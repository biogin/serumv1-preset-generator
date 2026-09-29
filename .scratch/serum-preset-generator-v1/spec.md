# Serum Preset Generator v1

Status: ready-for-agent

## Problem Statement

I produce music every day in Serum 1. I often have a sound in my head that I can describe in words ("aggressive, overdriven cyberpunk bass that leaves the sub clean") but don't know how to build in Serum. Reading the manual and watching tutorials every time is slow and breaks my flow. I want to describe the sound and get something I can load and play right away, plus an explanation I can learn from.

I'm also looking for work and want this project to show an agentic LLM stack (MCP, LangGraph, a local/cloud model switch, and an eval harness) built with deliberate, measured trade-offs.

## Solution

A local tool that turns a **Sound Description** into:

- a **Patch Recipe**: step-by-step Serum settings, module by module, with the reasoning, in the language of the Sound Description and using Serum's on-screen names, and
- a **Preset**: a Serum 1 `.fxp` file saved into a dedicated `User/AI` folder in Serum's preset library, ready to click in Serum's browser.

I use it by chatting in Claude Desktop or Claude Code, which call the tool's `design_patch` MCP tool, or offline from a `serum-gen` command-line tool. Inside the tool, a LangGraph pipeline plans the sound, drafts parameter values, validates them against the **Parameter Reference**, retries with the errors when validation fails, and writes the Preset. The pipeline's model is configurable: Claude Sonnet 5.5 by default, or a local Ollama model for offline use.

## User Stories

1. As a producer, I want to describe a sound in plain language, so that I don't have to know which Serum controls to use.
2. As a producer, I want to write my Sound Description in Russian or English, so that I can describe sounds the way I think about them.
3. As a producer, I want the Patch Recipe in the language of my Sound Description, so that I can follow it easily.
4. As a producer, I want the Patch Recipe to use Serum's exact on-screen names (e.g. `Diode 1`, `Hyper/Dimension`, `LFO 1 → Cutoff`), so that I can find every control on screen.
5. As a producer, I want the Patch Recipe organised module by module (oscillators, sub, noise, filter, envelopes, LFOs, mod matrix, FX, macros), so that I can build or check it in the order Serum's UI shows it.
6. As a producer, I want each step of the Patch Recipe to say why it was chosen, so that I learn sound design instead of copying values.
7. As a producer, I want a Preset file written automatically, so that I can load the sound without dialling it in by hand.
8. As a producer, I want Presets saved in a dedicated `User/AI` folder in Serum's preset library, so that I can find them in Serum's browser and they never mix with factory or my own presets.
9. As a producer, I want an existing Preset never to be overwritten, getting a numbered name (`cyber_bass_2.fxp`) instead, so that I never lose an earlier result.
10. As a producer, I want the Preset's file name and in-Serum preset name derived from my Sound Description, so that I can tell Presets apart in the browser.
11. As a producer, I want the tool to tell me the full path of the written Preset, so that I know where to look.
12. As a producer, I want to be told if Serum needs a folder rescan to show new Presets, so that I'm not confused when a Preset doesn't appear.
13. As a producer, I want constraints in my Sound Description (e.g. "keep the sub clean", "no reverb", "mono") respected in the result, so that the sound fits my mix.
14. As a producer, I want the tool to pick factory wavetables by name for the oscillators, so that the Preset loads without missing files.
15. As a producer, I want the tool to use oscillators A and B, the sub and noise oscillators, the filter, envelopes 1–3, LFOs 1–4 (built-in shapes), the mod matrix, all FX modules and the macros, so that it can reach the sound the way a sound designer would.
16. As a producer, I want modulation routings (e.g. LFO 1 → filter cutoff) written into the Preset's mod matrix, so that movement in the sound works when the Preset loads.
17. As a producer, I want every parameter not set by the tool left at Serum's Init value, so that the Preset has no leftover settings.
18. As a producer, I want invalid or out-of-range values caught and corrected automatically before a Preset is written, so that I never get a broken Preset.
19. As a producer, I want to be told if the tool couldn't produce a valid patch after its retries, and why, so that I can rephrase instead of getting a silently wrong Preset.
20. As a producer, I want to call the tool from Claude Desktop or Claude Code, so that I can use it in a chat I already have open.
21. As a producer, I want to ask follow-up questions in the same chat (e.g. "why Diode 1?"), so that I understand the result.
22. As a producer, I want a `serum-gen "<sound description>"` command-line tool that prints the Patch Recipe and writes the Preset, so that I can use it without a chat app.
23. As a producer, I want the tool to run fully offline with a local model, so that I can use it without an internet connection or API costs.
24. As a producer, I want to switch between the cloud model and the local model with one setting, so that I can choose quality or offline use per session.
25. As a producer, I want the tool to tell me which model produced a result, so that I can judge quality in context.
26. As a producer, I want a result in well under a minute with the cloud model, so that it doesn't break my flow.
27. As a job seeker, I want a test set of 10–15 Sound Descriptions (bass, lead, pad, pluck, FX; Russian and English), so that I can measure quality instead of guessing.
28. As a job seeker, I want automatic checks on every test-set result (Preset reads back, all parameters in range, constraints met, retry count), so that regressions are caught.
29. As a job seeker, I want to record my own 1–5 ear rating per test-set result in a results file, so that quality includes how it actually sounds.
30. As a job seeker, I want to run the test set against both the cloud and the local model and compare them, so that I can show the trade-off with numbers.
31. As a job seeker, I want each pipeline run traceable step by step (plan, each draft, each validation error, write), so that I can debug it and show how the agent works.
32. As a developer, I want the `.fxp` reader to decode any factory Serum 1 preset into named parameters, so that Presets can be verified now and used as Reference Presets later.
33. As a developer, I want reading and then writing a factory preset to give identical bytes, so that I trust the writer.
34. As a developer, I want the Parameter Reference to be the single source of truth for parameter names, ranges, options and positions, so that the writer, the validator and the model's prompt never disagree.
35. As a developer, I want the pipeline testable without a network or API key, so that the normal test run is fast and free.
36. As a developer, I want the output folder configurable, so that tests and experiments never write into the real Serum library.
37. As a developer, I want the model provider and model name configurable, so that swapping models needs no code change.
38. As a developer, I want the MCP server and the command-line tool to be thin wrappers over the same pipeline, so that behaviour is identical in both.

## Implementation Decisions

- **Target: Serum 1 v1.368 only** (ADR 0001). Presets are `.fxp`.
- **Modules:**
  - **FXP codec**: a deep module. Its interface is roughly `read(bytes) → Patch` and `write(Patch) → bytes`.
    - It handles the VST2 opaque-chunk container, the two zlib streams and the trailer, the 299 normalised float parameters, the mod-matrix records, and the oscillator wavetable name strings.
    - Writing starts from an Init template `.fxp` that the owner saves from Serum. Everything the Patch doesn't set keeps the template's value.
    - The spec for the byte layout is `btesser/serum2vital`'s FORMATS.md; its `craft_fxp.py` is the reference implementation to check against. We write our own implementation, not a vendored one.
    - Known pitfalls:
      - If the trailer is wrong, Serum silently loads Init.
      - The filter-type index divisor varies across Serum builds. Pin it to v1.368 by checking against factory presets.
      - Some parameter names in the older 0xdevalias gist are wrong.
  - **Parameter Reference**: static data. Each entry has the Serum on-screen name, the module, the value type (continuous range with units, or a list of options such as filter types), the default, and the position in the preset. It also lists valid mod sources and destinations and factory wavetable names. The codec, the validator and the draft prompt all use it.
  - **Patch**: the structured intermediate between the model and the codec. It holds values by Parameter Reference name in human units or option names, plus mod-matrix routings and wavetable names. Conversion to normalised floats happens only in the codec.
  - **Validator**: pure code, no LLM. It checks a draft Patch against the Parameter Reference: names exist, values are in range, options are valid, mod routings are legal, and wavetables exist. It also checks constraints extracted during planning (e.g. clean sub → the sub path is not distorted or is high-passed as planned). It returns a list of human-readable errors.
  - **Pipeline**: a LangGraph graph (ADR 0002).
    - Nodes: `plan` → `draft` → `validate` → (retry `draft` with errors, at most 3 times) → `write`.
      - `plan` turns the Sound Description into a structured brief: sound category, character, checkable constraints, language.
      - `draft` produces the Patch plus the Patch Recipe text as structured output.
      - `write` names the file, avoids collisions and calls the codec.
    - No retrieval step in v1 (ADR 0003).
    - Returns a result with the Patch Recipe, the Preset path, the model used, and a validation report (checks run, pass/fail, retry count). If retries run out, it returns the last errors and writes no Preset.
  - **Model provider**: every node calls the model through LangChain's chat-model interface.
    - Config picks `anthropic` (default `claude-sonnet-5-5`) or `ollama`. The default local model is a ~8B instruct model, sized for the owner's 16 GB Mac.
    - Structured output uses JSON-schema-constrained generation on both providers, so option values such as filter types can only come from the Parameter Reference.
  - **MCP server**: built with the official `mcp` Python SDK over stdio and registered in Claude Desktop and Claude Code. It exposes a single tool, `design_patch(sound_description)`, and returns the Patch Recipe, the Preset path and a one-line note on how to find it in Serum.
  - **CLI**: `serum-gen "<sound description>"` with a flag to pick the model provider. It prints the Patch Recipe and the Preset path.
  - **Config**: model provider and model name, API key from the environment, output folder, Init template location, retry limit. Default output folder: Serum's `Presets/User/AI` folder.
- **Tooling:** Python 3.12, `uv`, `pytest`, `ruff`, LangGraph, `langchain-anthropic`, `langchain-ollama`, and the `mcp` SDK.

## Testing Decisions

- Good tests exercise external behaviour through the two agreed seams only. They assert on returned results and on the bytes and files produced, never on internal node order, prompt text or private helpers.
- **Seam 1: pipeline `design_patch(sound_description)`.**
  - Setup: tests inject a fake chat model with scripted responses via config, and point the output folder at a temporary directory.
  - Cases:
    - a valid draft writes a Preset that reads back as the same Patch
    - an invalid draft triggers a retry carrying the validator's errors
    - running out of retries writes no Preset and reports the errors
    - a name collision produces `_2`
    - constraint checks pass or fail as expected
    - the recipe language follows the Sound Description
  - Wrappers: the MCP server and CLI each get one smoke test through this seam.
- **Seam 2: FXP codec `read`/`write`.**
  - Byte round-trip over the installed factory presets (459 files). Skipped if the library isn't present, so CI doesn't depend on it.
  - Known-value checks on a few chosen factory presets, e.g. filter type, a mod routing, oscillator wavetable name.
  - Editing one parameter, writing and reading back changes only that parameter.
  - Writes from the Init template reproduce the template's bytes when the Patch is empty.
- **Test set (eval).** It uses Seam 1 with a real model and runs on its own under a separate pytest marker, so it's excluded from the default run.
  - Records per case: validity, retry count, constraint results, model, and time taken.
  - Writes a results file with an empty column for the owner's 1–5 ear rating.
- **Manual acceptance:** at least one generated Preset loads in Serum 1 and sounds like its Sound Description.
- **Prior art:** none. This is a new repo.

## Out of Scope

- Serum 2 and any synth other than Serum 1.
- Retrieval / LlamaIndex / Knowledge Base ingestion and the `search_knowledge` tool (v1.1 experiment, ADR 0003).
- Reference Presets used as examples in prompts (v1.1).
- `revise_patch(preset, feedback)` for changing an existing Preset (v1.1).
- Starting from the closest Reference Preset instead of Init.
- Custom or generated wavetables, and hand-drawn LFO shapes.
- Rendering Presets to audio and checking the audio (v2).
- A FastAPI HTTP API or any web UI.
- LM Studio or any other offline chat host.
- Loading a Preset into a running Serum instance automatically.

## Further Notes

- Serum 1.368 is installed (VST, VST3, AU). The factory library, including `Serum_Manual.pdf`, is at `/Library/Audio/Presets/Xfer Records/Serum Presets/`. The presets folder is world-writable and already has an empty `User/` subfolder.
- **Owner action needed:** save an Init preset from Serum (menu → Init Preset → Save As) for the codec's write template. No plain Init `.fxp` exists in the factory library.
- **Verified 2026-09-29 (ticket 02):** Serum 1's browser shows a newly written Preset immediately while Serum is open, with no rescan or reopening needed. The MCP/CLI output note only has to say where to find it (`User/AI`).
- Local-model quality on 16 GB will trail Sonnet noticeably. The validator and constrained output are the mitigation, and the test set measures the gap.
- References:
  - https://github.com/btesser/serum2vital (docs/FORMATS.md, tools/craft_fxp.py)
  - https://gist.github.com/0xdevalias/135a18e979ac8e302ebbc700a50a8d74
- Glossary: `CONTEXT.md`. Decisions: `docs/adr/0001`–`0003`.
