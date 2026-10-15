# Serum Preset Generator

Validates and writes Xfer Serum 1 settings as a loadable preset. Turning a producer's plain-language description into those settings is the calling MCP client's job, not this project's — see ADR 0004.

## Language

**Patch**:
A complete set of Serum settings in human terms (values by Parameter Reference name, in real units or option names, plus wavetables and Routings). A Preset stores a Patch, and a Patch Summary reports one.
_Avoid_: sound, settings, state

**Patch Summary**:
The short, structured list of exact settings/values a tool call returns alongside the written Preset's path — plain facts (which Parameter Reference names and values were touched), not prose reasoning. The calling MCP client turns a producer's sound description into the Patch in the first place and explains its own reasoning to the producer directly in chat; nothing in this project writes that explanation, only the facts the client can quote.
_Avoid_: Patch Recipe (retired; implied a server-generated explanation that no longer exists — see ADR 0004), recipe, steps, instructions

**Routing**:
One modulation-matrix slot: a modulation source (an LFO, envelope, macro...) moving a destination parameter by an amount from -100 to 100 %, optionally bipolar. A Patch holds up to 32, in slot order.
_Avoid_: mod, connection, mod slot

**Constraint**:
A hard requirement on the resulting sound (clean sub, no reverb, no distortion, mono), checked by code against the whole Patch before a Preset is written.
_Avoid_: rule, requirement

**Preset**:
A Serum 1 `.fxp` file that loads the patch directly in Serum's browser.
_Avoid_: patch file, fxp (in prose)

**Revision**:
A new Preset made from an existing one by applying a partial Patch update. Its Patch Summary lists only what changed; the original Preset is never modified.
_Avoid_: edit, update, tweak, version

**Parameter Reference**:
The authoritative list of Serum 1's parameters: each one's name as shown in Serum, its allowed range or options, and its place in the preset.
_Avoid_: schema, param table, param map

**Reference Preset**:
An existing Serum preset (factory or the producer's own) decoded into readable parameters and used as a worked example of values that produce a named sound.
_Avoid_: example preset, sample preset
