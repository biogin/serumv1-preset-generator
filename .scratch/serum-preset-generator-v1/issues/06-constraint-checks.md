# 06: Constraint checks

**What to build:** Constraints in a Sound Description are respected, or you get a clear failure. `plan` extracts constraints that code can check ("keep the sub clean", "no reverb", "mono", …) into the brief. The validator checks them against the draft Patch, and failures feed back into the retry like any other validation error. When retries run out, the result says which constraints failed and why, and no Preset is written. The validation report lists every constraint check and its result.

**Blocked by:** 03 (Tracer bullet), 04 (The full Parameter Reference)

**Status:** done

- [x] The brief from `plan` carries structured, checkable constraints drawn from a defined set (at minimum: clean sub, no reverb, mono, no distortion)
- [x] Each constraint has a deterministic check against the Patch (e.g. clean sub → the sub path is undistorted or high-passed as planned)
- [x] Failed constraints appear as human-readable validator errors and trigger a retry
- [x] The validation report lists each constraint with pass/fail
- [x] Seam tests with scripted drafts cover a violating draft → retry → passing draft, and a draft that never satisfies the constraint → no Preset plus reported reasons

## Comments

- Implemented four constraints: clean_sub, no_reverb, no_distortion and mono. Each has a deterministic check (`constraints.py`) against the whole Patch: Init values plus the draft, Routings included.
- `plan` lists the constraints the description states. Failed checks feed back into the retry with concrete fixes. The report and CLI show each constraint as ✓/✗; constraints that were never checked (the draft failed earlier) are omitted rather than shown as failed.
- The checks model Serum's signal flow:
  - The FX rack (Distortion, FX Filter, Reverb) processes the whole output, sub included.
  - Only oscillators routed through the filter get its drive or a distorting type (Dist.Comb, Scream, SampHold, Ring Mod).
  - The "Reverb" filter type counts as reverb.
  - Modulating a drive or pan counts as using it.
  - Mono also covers delay L/R differences, Fil Stereo, FX Fil Pan and unison spread. Stereo FX at 0 % mix are allowed.
- Deliberately strict:
  - "clean sub" means Osc S;
  - any active Distortion FX breaks clean_sub, including an HP pre-filter setup whose dry-signal behaviour isn't verified.
- Live run with "aggressive, overdriven cyberpunk bass that leaves the sub clean":
  1. `plan` extracted clean_sub.
  2. Draft 1 enabled the Distortion FX and was rejected.
  3. Draft 2 used a Scream LP filter at drive 65 with OscS>Fil Off, and passed. The recipe explains why.
- Optional check by ear: `User/AI/Cyberpunk Clean Sub Bass`.
