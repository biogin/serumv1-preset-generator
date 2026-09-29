# 03: Tracer bullet: `serum-gen "<sound description>"` end to end

**What to build:** Running `serum-gen "<sound description>"` prints a Patch Recipe and writes a Preset into Serum's `User/AI` folder. For now it only uses the starter Parameter Reference.

The work runs through the LangGraph pipeline (ADR 0002) on Claude Sonnet 5.5: `plan` → `draft` → `validate` → retry `draft` with the validator's errors (at most 3 times) → `write`. There is no retrieval step (ADR 0003).

- The Patch Recipe is written in the Sound Description's language and uses Serum's on-screen names, with the reasoning for each step.
- Existing files are never overwritten (`name_2.fxp`).
- Each step is logged so a run can be traced.

This ticket introduces the pipeline seam, `design_patch(sound_description)`, which returns the Patch Recipe, the Preset path, the model used and a validation report.

**Blocked by:** 02 (`.fxp` writer and the Init template)

**Status:** ready-for-agent

- [ ] `serum-gen "<sound description>"` prints the Patch Recipe and the Preset's full path
- [ ] The Preset is written to the configured output folder (default Serum's `Presets/User/AI`, created if missing), with a file name and preset name derived from the Sound Description
- [ ] A name collision produces a numbered file; nothing is ever overwritten
- [ ] The validator (pure code) rejects unknown parameter names, out-of-range values and invalid options, with human-readable errors
- [ ] Validation errors are fed back into `draft`; after 3 failed retries no Preset is written and the errors are reported
- [ ] The Patch Recipe follows the Sound Description's language (Russian or English)
- [ ] Config covers model provider/name, API key from the environment, output folder, Init template location and retry limit
- [ ] Seam tests with a scripted fake chat model and a temp output folder cover: valid draft → Preset reads back as the same Patch; invalid draft → retry with errors; retries exhausted → no Preset; collision naming
- [ ] Each pipeline step (plan, each draft, each validation result, write) is traceable in logs
- [ ] Manual check: one generated Preset loads in Serum 1
