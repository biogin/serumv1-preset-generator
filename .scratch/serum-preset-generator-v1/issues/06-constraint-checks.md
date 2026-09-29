# 06: Constraint checks

**What to build:** Constraints in a Sound Description are respected, or you get a clear failure. `plan` extracts constraints that code can check ("keep the sub clean", "no reverb", "mono", …) into the brief. The validator checks them against the draft Patch, and failures feed back into the retry like any other validation error. When retries run out, the result says which constraints failed and why, and no Preset is written. The validation report lists every constraint check and its result.

**Blocked by:** 03 (Tracer bullet), 04 (The full Parameter Reference)

**Status:** ready-for-agent

- [ ] The brief from `plan` carries structured, checkable constraints drawn from a defined set (at minimum: clean sub, no reverb, mono, no distortion)
- [ ] Each constraint has a deterministic check against the Patch (e.g. clean sub → the sub path is undistorted or high-passed as planned)
- [ ] Failed constraints appear as human-readable validator errors and trigger a retry
- [ ] The validation report lists each constraint with pass/fail
- [ ] Seam tests with scripted drafts cover a violating draft → retry → passing draft, and a draft that never satisfies the constraint → no Preset plus reported reasons
