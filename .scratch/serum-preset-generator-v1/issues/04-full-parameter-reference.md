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

**Status:** ready-for-human

- [x] All 299 parameters present, with names matching Serum's on-screen labels, not the older gist's wrong names
- [ ] Option lists (filter types, warp modes, FX types, etc.) and continuous ranges with units are correct for v1.368
- [x] Factory wavetable names come from the installed library, and the validator rejects unknown wavetables
- [x] Known-value tests on factory presets cover each module group (oscillators, filter, envelopes, LFOs, FX, macros)
- [x] `serum-gen inspect` shows the full parameter set
- [x] The draft prompt and validator use the full reference; a Sound Description that needs distortion or unison produces a valid Preset that uses them

## Comments

- Implemented all 299 parameters, with names exactly as Serum 1.368 reports them. That fixes the gist's names for 61-64, 83/85/87, 193, 260-263, 268 and 270-272.
- Each entry has a module and a Curve: Linear, Power, Exponential, Decibels, MakeupGain, Options, or Stepped for tempo-synced labels.
- Curves were checked against Serum's own read-outs at 229 knob positions: 29 curves in tests at 5 positions each, and the reviewer checked all positions. Remaining drift is Serum's display rounding, plus a slight drift near the bottom of Cmp_Thr (-105 vs -104 dB).
- Params 228-298 are read from the second block. Older presets (every factory preset) fall back to Serum's defaults for the untrusted tail, per FORMATS.md.
- Deliberate deviations and follow-ups:
  - **Defaults** come from the packaged Init preset (Serum 1.368 ground truth), not a per-entry field. The 1.334 listing's defaults are stale for the reverb and FX levels.
  - **"% of knob travel"** for parameters whose display mapping isn't known: FX Fil Freq, Dist_BW, A/B Warp, Spin Rate/Depth, Dly_Off L/R.
  - **Not settable by the model:**
    - the mod-matrix amt/out slots (ticket 05);
    - the tempo-sync switches, so note-value delay times and Hz FX rates stay truthful;
    - LFOs 5-8 (the scope is 1-4);
    - host-only controls: Mast.Tun, Amp., Pitch Bend, Mod Wheel, and the FX output trims.
  - **LFO shape and mode** are point data and switch bytes, not parameters, so LFOs keep Init's shape. LFO settings also do nothing until ticket 05 adds routing.
  - **Won't do:** clamping (out-of-range values are rejected so the model gets feedback and retries), typed parameter names, and offsets as reference data. The reference is the single source for names, and the codec owns byte positions.
- **Needs the owner:**
  - **SubOscShape:** stored as index/5 (six shapes), but Serum's captured menu lists five names. "Triangle" was inserted at index 2 from memory. Check `Bass/BA D_Bass 2 [DU]` (expect Triangle) and `Bass/BA D_Bass 1 [DU]` (expect Saw).
  - Load `User/AI/Cyberpunk Drive Bass` (live run: unison, Osc B, sub, noise, filter, envelopes, Distortion, EQ, Compressor).
- Live run note: the recipe claimed "OscS>Fil Off" keeps the sub clean, but the FX rack still distorts it. Catching this is ticket 06's job.
