# 07: Local model option

**What to build:** `serum-gen` works fully offline. The model is configuration (ADR 0002): a config setting and a CLI flag choose `anthropic` (default, Claude Sonnet 5.5) or `ollama`. The default local model is a ~8B instruct model that fits a 16 GB Mac. Both providers use output constrained to a JSON schema, so option values can only come from the Parameter Reference. Every result names the model that produced it.

**Blocked by:** 03 (Tracer bullet)

**Status:** wontfix — moot. [ADR 0004](../../../docs/adr/0004-no-model-in-the-server.md) removes the model from this codebase entirely; there's no provider left to make configurable, local or otherwise.

- [ ] Switching provider needs only config or the CLI flag, with no code change
- [ ] With `ollama` selected and the network off, `serum-gen "<sound description>"` produces a Patch Recipe and Preset (or a clear validation failure)
- [ ] Structured output is schema-constrained on both providers
- [ ] The result and the CLI output show provider and model name
- [ ] A clear error when Ollama isn't running or the model isn't pulled, including the command to fix it
- [ ] Seam tests still run with the fake model and need no network or API key
