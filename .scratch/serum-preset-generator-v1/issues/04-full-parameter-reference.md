# 04: The full Parameter Reference

**What to build:** The Parameter Reference covers all 299 Serum 1 parameters. The pipeline can now draft sounds using every module in scope:
- oscillators A and B (wavetable, position, unison, detune, warp)
- the sub and noise oscillators
- the filter
- envelopes 1–3
- LFOs 1–4 (built-in shapes only)
- all FX modules
- macros

Each entry has Serum's on-screen name, the module, the value type (range with units, or an option list) and the default. The reference also lists the factory wavetable names, so oscillators pick existing wavetables by name. Custom wavetables and hand-drawn LFO shapes stay out of scope.

**Blocked by:** 02 (`.fxp` writer and the Init template). Can run in parallel with 03.

**Status:** ready-for-agent

- [ ] All 299 parameters present, with names matching Serum's on-screen labels, not the older gist's wrong names
- [ ] Option lists (filter types, warp modes, FX types, etc.) and continuous ranges with units are correct for v1.368
- [ ] Factory wavetable names come from the installed library, and the validator rejects unknown wavetables
- [ ] Known-value tests on factory presets cover each module group (oscillators, filter, envelopes, LFOs, FX, macros)
- [ ] `serum-gen inspect` shows the full parameter set
- [ ] The draft prompt and validator use the full reference; a Sound Description that needs distortion or unison produces a valid Preset that uses them
