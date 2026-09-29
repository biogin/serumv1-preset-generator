# 02: `.fxp` writer and the Init template

**What to build:** The FXP codec can write Presets. Reading a factory preset and writing it back gives identical bytes. Setting a Patch on the Init template produces a Preset that Serum 1 loads with exactly those changes, with everything else left at Init values. This ticket also answers the open question of whether Serum's browser shows new files while it's open or needs a rescan.

Owner action first: save an Init preset from Serum (menu → Init Preset → Save As). The factory library has no plain Init `.fxp`.

**Blocked by:** 01 (Project setup and `.fxp` reader); the owner's saved Init preset

**Status:** ready-for-agent

- [ ] Byte round-trip: read → write is identical for every installed factory preset (skipped when the library isn't present)
- [ ] An empty Patch written on the Init template reproduces the template's bytes
- [ ] Editing one parameter, writing and reading back changes only that parameter
- [ ] The two zlib streams and the trailer are written correctly, so Serum doesn't silently fall back to Init
- [ ] Manual check: a Preset with a changed filter cutoff and Osc A wavetable loads in Serum 1 and shows those values
- [ ] Serum's rescan behaviour for new files is recorded in the spec's Further Notes
