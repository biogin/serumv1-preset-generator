# 09: Test set and comparison

**What to build:** A repeatable test set, so quality is measured rather than guessed. It has 10–15 Sound Descriptions covering bass, lead, pad, pluck and FX, in both Russian and English, several with constraints. It runs through the pipeline seam with a real model under its own pytest marker, excluded from the default run. It can run against Claude Sonnet 5.5 and the local Ollama model.

Each run writes a results file. Per case it records:
- whether the Preset is valid and reads back
- the retry count
- constraint results
- the model used
- the time taken
- an empty column for the owner's 1–5 ear rating

A short summary compares the two models.

**Blocked by:** 05 (The mod matrix), 06 (Constraint checks), 07 (Local model option)

**Status:** ready-for-agent

- [ ] 10–15 test Sound Descriptions stored as data, mixing categories and languages, several with constraints
- [ ] The test set runs under a dedicated pytest marker and is excluded from the default `pytest` run
- [ ] It can be run against either provider with one option
- [ ] The results file has one row per case with validity, read-back, retries, constraint results, model, time and an empty ear-rating column
- [ ] Generated Presets from a test run go to a separate output folder, not the real `User/AI` folder, unless asked
- [ ] A summary (valid rate, mean retries, constraint pass rate, mean time) per model, suitable for the README
