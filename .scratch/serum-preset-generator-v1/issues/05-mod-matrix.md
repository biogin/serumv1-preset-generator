# 05: The mod matrix

**What to build:** Presets can carry modulation. The FXP codec reads and writes mod-matrix routings (source, destination, amount, bipolar). The Parameter Reference lists legal sources and destinations, and the validator rejects illegal routings. The pipeline can draft routings like "LFO 1 → Filter Cutoff", and they work when the Preset loads. The Patch Recipe lists each routing with its reasoning.

**Blocked by:** 03 (Tracer bullet), 04 (The full Parameter Reference)

**Status:** ready-for-human

- [x] `serum-gen inspect` shows mod-matrix routings of factory presets, checked against known values in at least 2 presets
- [x] Routings written into a Preset read back identically; round-trip tests still pass
- [x] The validator rejects unknown sources/destinations, out-of-range amounts and more routings than the matrix holds
- [x] Seam test: a scripted draft with routings produces a Preset whose read-back routings match
- [ ] Manual check: a generated Preset with an LFO → cutoff routing audibly moves in Serum 1

## Comments

- Implemented. Findings from the factory library that go beyond FORMATS.md:
  - The slot byte in the record marker is 0-based.
  - The record amount equals the "Mod N amt" parameter in all 3,736 routings, so both are written.
  - The +0x18 field is Serum's destination-menu position and is a strict function of the destination index. It is known for the 110 destinations the library uses, and only those can be written.
  - Empty slots store menu 173 / destination 316.
- Source ids differ between builds:
  - The factory library (older builds) uses 17-20 where the evidence points to Macros 1-4.
  - A preset the owner saved with Serum 1.368 uses 24/25 for macros, matching FORMATS.md.
  - Writing uses the current table, and only onto current-build bases (the Init template). Reading older presets maps ids 1-12 and 17-20; other ids show as "Source N (older Serum build)".
- The model sees designable sources (no LFO 5-8, MPE or Fixed) and the 110 destinations. The recipe prompt asks for a "Modulation" step explaining each routing.
- Unverified until the manual check: the first float of a record is written as (amount+1)/2, which matches empty slots (0.5).
- "Mod N out" is written at 100 %, like 3,688 of the 3,697 factory routings.
- Live run: "dubstep wobble bass …" produced LFO 1 (1/8) → Fil Cutoff 55 % and Env 2 → Fil Cutoff 40 %, with the filter on (`User/AI/Dubstep Wobble Bass 18 Pluck`).
- **Still open, needs the owner:** load that Preset. The Matrix should show both routings, and the filter should audibly wobble in 1/8 and pluck on each note.
