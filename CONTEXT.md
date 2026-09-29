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
A complete set of Serum settings in human terms (values by Parameter Reference name, in real units or option names, plus wavetables). A Preset stores a Patch, and a Patch Recipe explains one.
_Avoid_: sound, settings, state

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
