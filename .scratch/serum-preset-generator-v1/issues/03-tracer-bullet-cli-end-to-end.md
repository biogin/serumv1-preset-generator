# 03: Tracer bullet: `serum-gen "<sound description>"` end to end

**What to build:** Running `serum-gen "<sound description>"` prints a Patch Recipe and writes a Preset into Serum's `User/AI` folder. For now it only uses the starter Parameter Reference.

The work runs through the LangGraph pipeline (ADR 0002) on Claude Sonnet 5.5: `plan` → `draft` → `validate` → retry `draft` with the validator's errors (at most 3 times) → `write`. There is no retrieval step (ADR 0003).

- The Patch Recipe is written in the Sound Description's language and uses Serum's on-screen names, with the reasoning for each step.
- Existing files are never overwritten (`name_2.fxp`).
- Each step is logged so a run can be traced.

This ticket introduces the pipeline seam, `design_patch(sound_description)`, which returns the Patch Recipe, the Preset path, the model used and a validation report.

**Blocked by:** 02 (`.fxp` writer and the Init template)

**Status:** ready-for-human

- [x] `serum-gen "<sound description>"` prints the Patch Recipe and the Preset's full path
- [x] The Preset is written to the configured output folder (default Serum's `Presets/User/AI`, created if missing), with a file name and preset name derived from the Sound Description
- [x] A name collision produces a numbered file; nothing is ever overwritten
- [x] The validator (pure code) rejects unknown parameter names, out-of-range values and invalid options, with human-readable errors
- [x] Validation errors are fed back into `draft`; after 3 failed retries no Preset is written and the errors are reported
- [x] The Patch Recipe follows the Sound Description's language (Russian or English)
- [x] Config covers model provider/name, API key from the environment, output folder, Init template location and retry limit
- [x] Seam tests with a scripted fake chat model and a temp output folder cover: valid draft → Preset reads back as the same Patch; invalid draft → retry with errors; retries exhausted → no Preset; collision naming
- [x] Each pipeline step (plan, each draft, each validation result, write) is traceable in logs
- [ ] Manual check: one generated Preset loads in Serum 1

## Comments

- Implemented. Live runs on claude-sonnet-5-5 (~15 s each):
  - an English description → `Cyberpunk Clean Sub Drive.fxp` with an English recipe;
  - a Russian description → `Tyomnyy Myagkiy Ambient Pad.fxp`, with a Russian recipe that keeps Serum's names in English.
  All passed validation on the first draft.
- Model call details:
  - structured output uses `method="json_schema"` (Sonnet 5.5 rejects forced tool use), at effort `medium`;
  - the server-side refusal fallback is on (`fallbacks: "default"`), and the result names the model that actually answered;
  - a response that doesn't match the schema counts as a validation error and is retried.
- Config: `SERUM_GEN_PROVIDER` accepts only `anthropic` for now; any other value is a clear error until ticket 07. Other settings: model, effort, output dir, template, Serum root, retries. `.env` is read from the working directory and the project root.
- Logging: each step logs at INFO; `serum-gen -v` shows the trace.
- Beyond the ticket:
  - wavetable names are validated against the installed `Tables` folder and listed in the draft prompt (spec story 14);
  - Presets are created exclusively (never overwrite), and numbered names are trimmed to fit 31 characters.
- `serum-gen inspect <file.fxp>` still inspects; any other description starting with "inspect" is designed.
- **Still open, needs the owner:** load one generated Preset from `User/AI` in Serum 1.
