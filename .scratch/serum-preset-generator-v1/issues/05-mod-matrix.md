# 05: The mod matrix

**What to build:** Presets can carry modulation. The FXP codec reads and writes mod-matrix routings (source, destination, amount, bipolar). The Parameter Reference lists legal sources and destinations, and the validator rejects illegal routings. The pipeline can draft routings like "LFO 1 → Filter Cutoff", and they work when the Preset loads. The Patch Recipe lists each routing with its reasoning.

**Blocked by:** 03 (Tracer bullet), 04 (The full Parameter Reference)

**Status:** ready-for-agent

- [ ] `serum-gen inspect` shows mod-matrix routings of factory presets, checked against known values in at least 2 presets
- [ ] Routings written into a Preset read back identically; round-trip tests still pass
- [ ] The validator rejects unknown sources/destinations, out-of-range amounts and more routings than the matrix holds
- [ ] Seam test: a scripted draft with routings produces a Preset whose read-back routings match
- [ ] Manual check: a generated Preset with an LFO → cutoff routing audibly moves in Serum 1
