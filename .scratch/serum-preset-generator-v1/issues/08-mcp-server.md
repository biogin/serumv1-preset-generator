# 08: MCP server

**What to build:** You can ask for a sound in Claude Desktop or Claude Code and get the Preset. It's an MCP server built with the official `mcp` Python SDK over stdio, and it exposes one tool, `design_patch(sound_description)`. The tool is a thin wrapper over the same pipeline as the CLI. It returns the Patch Recipe, the Preset path, the model used, and a one-line note on finding the Preset in Serum's browser (including any rescan step found in ticket 02). The chat host answers follow-up questions itself; there is no `search_knowledge` tool in v1 (ADR 0003).

**Blocked by:** 03 (Tracer bullet)

**Status:** done

- [x] The MCP server starts over stdio and lists exactly one tool, `design_patch`, with a clear description and input schema
- [x] Calling `design_patch` runs the pipeline and returns the Patch Recipe, the Preset path, the model and the Serum browser note
- [x] Validation failures come back as a readable tool result, not a crash
- [x] Setup instructions (in the README) register the server in Claude Desktop and Claude Code
- [x] Smoke test: an in-process MCP client calls `design_patch` with the fake model and gets a result
- [x] Manual check: a request from Claude Desktop produces a Preset that appears in Serum's `User/AI` folder

## Comments

- Implemented with the `mcp` 2.2.0 SDK (`MCPServer`; FastMCP was renamed in 2.x). The `serum-gen-mcp` entry point serves one tool, `design_patch(sound_description)`, over stdio.
- The CLI and the MCP tool share their output text (`presentation.py`) and environment loading (`config.resolve`). `.env` is read from the project folder, so the client needs no key in its environment.
- Error handling:
  - validation failures come back as a readable tool error;
  - setup, API and file errors (missing key, bad `SERUM_GEN_*`, unwritable folder) come back with their reason, not the SDK's bare "Error executing tool".
- Verified: launched by absolute `uv` path from another working directory, it serves over stdio and lists exactly one tool.
- Registered 2026-09-29, with the owner's approval:
  - Claude Code: `claude mcp add serum-gen --scope user`; `claude mcp list` shows it ✔ Connected.
  - Claude Desktop: added to `claude_desktop_config.json`; the original is backed up as `claude_desktop_config.json.bak-serum-gen-2026-09-29`.
- **Still open, needs the owner:** restart Claude Desktop and ask it for a preset; the Preset should appear in `User/AI`.
- 2026-09-29: owner asked Claude Desktop for a preset. It worked end to end.
- 2026-10-15: [ADR 0004](../../../docs/adr/0004-no-model-in-the-server.md) replaced `design_patch(sound_description)` with `write_patch(patch, constraints)`, plus new `edit_patch`/`list_parameters`/`describe_preset` tools. The server itself (stdio, `MCPServer`, shared `presentation.py` output, readable-not-crashing error handling) is unchanged; only the tool surface and what it validates/writes changed — there is no model call inside this process anymore.
