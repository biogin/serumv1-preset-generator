# Serum Preset Generator

Turns a producer's plain-language description of a sound into settings for Xfer Serum 1: a readable recipe and a loadable preset, grounded in the Serum manual and synthesis know-how.

## Language

**Sound Description**:
The producer's free-text request for a sound, e.g. "aggressive, overdriven cyberpunk bass that leaves the sub clean".
_Avoid_: prompt, query, request

**Patch Recipe**:
A human-readable, step-by-step list of Serum settings (module by module) that produces the described sound, with the reasoning behind each choice.
_Avoid_: steps, instructions, patch notes

**Patch**:
A complete set of Serum settings in human terms (values by Parameter Reference name, in real units or option names, plus wavetables and Routings). A Preset stores a Patch, and a Patch Recipe explains one.
_Avoid_: sound, settings, state

**Routing**:
One modulation-matrix slot: a modulation source (an LFO, envelope, macro...) moving a destination parameter by an amount from -100 to 100 %, optionally bipolar. A Patch holds up to 32, in slot order.
_Avoid_: mod, connection, mod slot

**Constraint**:
A hard requirement a Sound Description explicitly states (clean sub, no reverb, no distortion, mono), checked by code against the whole Patch before a Preset is written.
_Avoid_: rule, requirement

**Preset**:
A Serum 1 `.fxp` file that loads the patch directly in Serum's browser.
_Avoid_: patch file, fxp (in prose)

**Knowledge Base**:
The collection of reference material the generator draws on: the Serum manual, synthesis articles, and tutorials from forums and YouTube.
_Avoid_: docs, corpus, memory

**Parameter Reference**:
The authoritative list of Serum 1's parameters: each one's name as shown in Serum, its allowed range or options, and its place in the preset.
_Avoid_: schema, param table, param map

**Reference Preset**:
An existing Serum preset (factory or the producer's own) decoded into readable parameters and used as a worked example of values that produce a named sound.
_Avoid_: example preset, sample preset
