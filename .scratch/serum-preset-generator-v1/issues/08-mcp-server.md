# 08: MCP server

**What to build:** You can ask for a sound in Claude Desktop or Claude Code and get the Preset. It's an MCP server built with the official `mcp` Python SDK over stdio, and it exposes one tool, `design_patch(sound_description)`. The tool is a thin wrapper over the same pipeline as the CLI. It returns the Patch Recipe, the Preset path, the model used, and a one-line note on finding the Preset in Serum's browser (including any rescan step found in ticket 02). The chat host answers follow-up questions itself; there is no `search_knowledge` tool in v1 (ADR 0003).

**Blocked by:** 03 (Tracer bullet)

**Status:** ready-for-agent

- [ ] The MCP server starts over stdio and lists exactly one tool, `design_patch`, with a clear description and input schema
- [ ] Calling `design_patch` runs the pipeline and returns the Patch Recipe, the Preset path, the model and the Serum browser note
- [ ] Validation failures come back as a readable tool result, not a crash
- [ ] Setup instructions (in the README) register the server in Claude Desktop and Claude Code
- [ ] Smoke test: an in-process MCP client calls `design_patch` with the fake model and gets a result
- [ ] Manual check: a request from Claude Desktop produces a Preset that appears in Serum's `User/AI` folder
