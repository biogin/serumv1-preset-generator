# 01: Project setup and `.fxp` reader

**What to build:** Running `serum-gen inspect <preset>` on any factory Serum 1 preset prints its parameters by name. This is the first cut of the FXP codec's read side, backed by a starter Parameter Reference: master volume, filter type/cutoff/resonance, Osc A level, and both oscillators' wavetable names. It also sets up the Python project (Python 3.12, `uv`, `pytest`, `ruff`) that later tickets build on.

Use `btesser/serum2vital`'s FORMATS.md as the byte-layout spec and its code as a reference to check against. Write our own implementation. See ADR 0001 and the spec's FXP codec notes for the known pitfalls (two zlib streams plus trailer, filter-type divisor per Serum build, wrong names in the older gist).

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `uv` project with `pytest` and `ruff` configured; `uv run pytest` and `uv run ruff check` pass
- [x] `serum-gen inspect <preset>` prints the preset name and every starter Parameter Reference entry with its value in human units or its option name
- [x] Filter type decodes to the correct option name for Serum v1.368
- [x] Known-value tests on at least 3 chosen factory presets (e.g. a bass, a lead, a pad) pass, using values checked by eye in Serum
- [x] Every installed factory preset reads without error (test skipped when the factory library isn't present)
- [x] Parameter Reference is data consumed by the reader, not values hard-coded in reader logic

## Comments

- Implemented. The known-value literals come from btesser/serum2vital's independent reader and from Serum's own cutoff read-out table. **Still open: the owner checks them by eye in Serum:**
  - BA Ampology: German LP at ~75 Hz, Osc A = Digital/Kream, A level ~40 %
  - LD Analogesque: MG Low 12, Osc A = Vowel/Native Curse, Osc B = Analog/PWM Juno
  - PD Beating Pad: cutoff ~198 Hz
  - LD LimoDriver: filter Formant-II (serum2vital decodes this one differently)
- Review follow-ups deferred to ticket 04 (full Parameter Reference):
  - move value conversion onto `Parameter`
  - add module and default fields
  - treat wavetable and preset-name positions as reference data
  - tighter parameter-name typing
  - clamp and NaN handling
- 2026-09-29: owner confirmed in Serum: BA Ampology (Kream, German LP, ~75 Hz) and LD LimoDriver (Formant-II) match. The saved Init preset (`User/ - Init - .fxp`) reads as Serum's documented Init values.
