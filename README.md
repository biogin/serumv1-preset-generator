# Serum 1 Preset Generator

Describe a sound in plain language ("aggressive cyberpunk bass that keeps the sub
clean", or in Russian) to whatever AI chat app you already use. It writes a
ready-to-load **Preset** straight into Xfer Serum 1's browser (`User → AI`).

- **No model, no API key, nothing to sign up for.** This server has no AI of its
  own — the chat app you're already using (Claude Desktop, Claude Code, or any
  other MCP-compatible app) does the sound design; this project only checks the
  result against a verified **Parameter Reference** and writes the file. See
  [`docs/adr/0004`](docs/adr/0004-no-model-in-the-server.md).
- **Makes nothing up.** Every value is checked against all 299 of Serum 1's real
  parameters (names, ranges, options) before anything is written, and the `.fxp`
  codec is tested byte-for-byte against the factory library.
- **Never loses work.** Writing a Preset never overwrites one — a name already
  in use gets `_2`, `_3`, and so on. Revising a preset always writes a new file;
  the original is untouched.
- **No network calls.** Nothing here calls any API or sends your data anywhere —
  it only reads and writes files on your own computer.

Design notes: [`CONTEXT.md`](CONTEXT.md) (glossary) and [`docs/adr/`](docs/adr/) (decisions).

## Install

Requires Serum 1 and an MCP-compatible chat app (Claude Desktop, Claude Code, or
similar). Nothing else — no account, no API key, no payment.

### Claude Desktop: one-click

Download **[the latest `.mcpb` file](https://github.com/biogin/serumv1-preset-generator/releases/latest)**
and double-click it — Claude Desktop installs it and asks you where your Serum
presets live (or just leave that blank to use the standard location).

### Not comfortable with any of this? Ask your AI to do it for you

Paste this into Claude Desktop, Claude Code, or any assistant with file/terminal
access on your computer:

```
Please set up the serumv1-preset-generator MCP server on this computer.

1. Install `uv` (a Python package manager) if it isn't already installed --
   on Mac/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   on Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

2. Register it as an MCP server pointed at
   https://github.com/biogin/serumv1-preset-generator (no need to clone it
   yourself -- `uv` fetches and builds it). If I'm on Claude Code, run:
   `claude mcp add serumv1-preset-generator -- uvx --from git+https://github.com/biogin/serumv1-preset-generator@v0.2.0 serum-gen-mcp`
   If I'm on Claude Desktop, add this to claude_desktop_config.json
   (Settings -> Developer -> Edit Config):
   {"mcpServers": {"serumv1-preset-generator": {"command": "uvx", "args":
   ["--from", "git+https://github.com/biogin/serumv1-preset-generator@v0.2.0",
   "serum-gen-mcp"]}}}

3. Tell me exactly what you did, then tell me to fully quit and restart my
   chat app (not just close the window) for it to take effect.

If you don't have file/terminal access to do this, say so and walk me through
the steps in this project's own README instead.
```

### Do it yourself

**Claude Code**, no clone needed, pinned to a stable release:

```sh
claude mcp add serumv1-preset-generator -- \
  uvx --from git+https://github.com/biogin/serumv1-preset-generator@v0.2.0 serum-gen-mcp
```

**Claude Desktop** (or any other MCP client): in *Settings → Developer → Edit
Config* (`~/Library/Application Support/Claude/claude_desktop_config.json`),
add this and restart:

```json
{
  "mcpServers": {
    "serumv1-preset-generator": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/biogin/serumv1-preset-generator@v0.2.0",
               "serum-gen-mcp"]
    }
  }
}
```

Then ask it, for example: *"Make me a Serum preset: warm evolving pad, no reverb"*,
or *"Make my Biggest Hard 808 preset hit harder."*

### For development, or to configure beyond the defaults

Clone the repo if you want `SERUM_GEN_SERUM_ROOT`, a custom Init template, or
anything else in Configuration below without passing env vars by hand:

```sh
git clone https://github.com/biogin/serumv1-preset-generator
cd serumv1-preset-generator
uv sync
claude mcp add serumv1-preset-generator --scope user -- \
  /opt/homebrew/bin/uv --directory "$(pwd)" run serum-gen-mcp
```

Use an absolute path for `uv` (Claude Desktop doesn't start servers with your
shell's `PATH`) — replace `/opt/homebrew/bin/uv` with the output of `which uv`.

## Tools

| Tool | Description |
|---|---|
| `write_patch(patch, constraints=[])` | Write a new preset from settings you designed. Returns a Patch Summary (the exact values written) and the Preset's path. |
| `edit_patch(preset, changes, constraints=[])` | Apply a partial change to an existing preset as a new Revision (`<name>_v2`, …); the original is never touched. Returns the Patch Summary plus every resulting difference. |
| `list_parameters()` | The full Parameter Reference: every settable name, its range/options and Init value, plus valid modulation sources/destinations and factory wavetables. Call this whenever you need an exact name or range. |
| `describe_preset(preset)` | A human-readable summary of an existing preset's current settings and modulation matrix. |

You don't write these calls by hand — the chat app you're using builds them
from your request, the same way it would call any other tool, guided by this
server's own instructions and `list_parameters()`.

## Command line

```sh
uv run serum-gen inspect path/to/preset.fxp   # every parameter and Routing of a preset
```

That's the only CLI command: designing or revising a preset from a description
needs a model, and there's no model in this codebase (see Install above) — so
there's nothing for a bare terminal command to call.

## Configuration

All settings are optional, set in the environment or `.env`:

| Variable | Default |
|---|---|
| `SERUM_GEN_OUTPUT_DIR` | Serum's `Presets/User/AI` |
| `SERUM_GEN_SERUM_ROOT` | `/Library/Audio/Presets/Xfer Records/Serum Presets` |
| `SERUM_GEN_TEMPLATE` | the packaged Init preset |

Developed and tested on macOS; Windows and Linux likely work too via
`SERUM_GEN_SERUM_ROOT` but are untested — there's no macOS-specific code
anywhere in this project.

## Known limitations

- **Revision quality is unverified on some cases.** `edit_patch` has worked
  well on presets like "Biggest Hard 808" + "hit harder," but at least one
  case ("PR 808 Kick Circuit [SD]" + "hit harder") didn't clearly change the
  sound as asked when tried with the old pipeline. Treat a Revision as a
  starting point to audition, not a guaranteed result.
- **Result quality tracks whatever chat app and model you're using** — this
  server has no sound-design opinion of its own.

## Development

```sh
uv run pytest        # no API key or network needed anywhere in this suite
uv run mypy          # strict
uv run ruff check && uv run ruff format --check
```

Tests that read the factory library skip when Serum isn't installed.

## Prior art

[serum-mcp](https://github.com/Celian-mrc/serum-mcp) does the same thing for
**Serum 2**, whose `.SerumPreset` format Xfer doesn't publish (its own docs
note parameters are shipped with confidence levels, not certainty). This
project targets **Serum 1**'s `.fxp` format instead, verified byte-for-byte
against the installed factory library — a different synth version, not a
better approach to the same one.

## License

[MIT](LICENSE)
