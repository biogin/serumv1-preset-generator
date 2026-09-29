# 02: `.fxp` writer and the Init template

**What to build:** The FXP codec can write Presets. Reading a factory preset and writing it back gives identical bytes. Setting a Patch on the Init template produces a Preset that Serum 1 loads with exactly those changes, with everything else left at Init values. This ticket also answers the open question of whether Serum's browser shows new files while it's open or needs a rescan.

Owner action first: save an Init preset from Serum (menu → Init Preset → Save As). The factory library has no plain Init `.fxp`.

**Blocked by:** 01 (Project setup and `.fxp` reader); the owner's saved Init preset

**Status:** ready-for-human

- [x] Byte round-trip: read → write is identical for every installed factory preset (skipped when the library isn't present)
- [x] An empty Patch written on the Init template reproduces the template's bytes
- [x] Editing one parameter, writing and reading back changes only that parameter
- [x] The two zlib streams and the trailer are written correctly, so Serum doesn't silently fall back to Init
- [ ] Manual check: a Preset with a changed filter cutoff and Osc A wavetable loads in Serum 1 and shows those values
- [ ] Serum's rescan behaviour for new files is recorded in the spec's Further Notes

## Comments

- Implemented. The Init template is the owner's `User/ - Init - .fxp`, now shipped in the package. Findings on the installed library that differ from FORMATS.md:
  - the second zlib stream varies in size (0 bytes to MBs, not a fixed 16 KB) and is kept verbatim;
  - the trailer is a single uint32 LE length of the first stream (not 8 bytes);
  - Serum compresses the state at zlib level 1, so recompression is byte-exact.
- The writer only writes values that differ from the base Preset, so unchanged options keep their original divisor.
- Out-of-range values and unknown parameter or option names are rejected, as are preset names Serum can't store (more than 31 characters, or non-latin-1 such as Cyrillic). The pipeline (ticket 03) must transliterate Russian names.
- **Still open, needs the owner:** load `User/AI Writer Test` in Serum (German LP, ~1200 Hz, 40 % reso, Osc A = PWM Juno), play a note, and report whether new files show up without a rescan. Then record the rescan answer in the spec's Further Notes.
- Unverified: setting a wavetable only swaps its name string. If Serum needs table data in the second stream, the manual check will show it.
