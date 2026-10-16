# Serum 1 Preset Generator

Describe a sound in plain language — "aggressive cyberpunk bass that keeps the
sub clean," or in Russian — to Claude Desktop, Claude Code, or another local
AI chat app on your own computer. You get a real, ready-to-load **Preset**
sitting in Xfer Serum 1's browser (`User → AI`).

It needs a local app, not claude.ai in a browser — it writes the Preset file
straight into Serum's folder on your machine, which a web chat can't reach.

- **Free, no sign-up.** Nothing to subscribe to, no API key to go get. If you
  can chat with Claude, you can use this.
- **Trustworthy.** Every setting is checked against all 299 of Serum 1's real
  parameters before anything is written, so you don't get a broken preset.
- **Never loses work.** It never overwrites an existing preset — a name
  that's taken gets `_2`, `_3`, and so on. Asking for a change always writes a
  new file; the one you started with is untouched.
- **Private.** It never sends anything anywhere — it only reads and writes
  files on your own computer.

Results aren't guaranteed to be perfect — always load the preset in Serum and
listen before you commit to it.

## Install (Claude Desktop)

1. Download **[the latest `.mcpb` file](https://github.com/biogin/serumv1-preset-generator/releases/latest)**.
2. Double-click it. Claude Desktop installs it and asks where your Serum
   presets live — leave that blank to use the standard location.
3. Restart Claude Desktop.

## Try it

Ask Claude something like:

- *"deep sub bass for a dark trap beat"*
- *"Make me a Serum preset: warm evolving pad, no reverb"*
- *"bright plucky arp for a melodic house drop"*
- *"warm pad, Don Toliver-ish"*, *"glassy pluck, Four Tet style"*, *"aggressive
  bass, Skrillex-ish"* — style and artist references work too; Claude draws on
  its general sense of that sound (genre, mood, typical gear), not an exact
  reproduction of any one track
- *"тёмный мягкий пэд"* — works in any language your chat app understands
- *"Make me a Serum preset: metallic FX riser"*, then *"make the one you just
  made darker"* — asking for a change always writes a new file; the original
  stays untouched

---

## For developers

### Other ways to install

Using Claude Code, or an MCP client other than Claude Desktop, pinned to a
stable release, no clone needed:

```sh
claude mcp add serumv1-preset-generator -- \
  uvx --from git+https://github.com/biogin/serumv1-preset-generator@v1.0.0 serum-gen-mcp
```

Any MCP client that reads a JSON config (Claude Desktop's own
`claude_desktop_config.json`, under *Settings → Developer → Edit Config*,
works the same way):

```json
{
  "mcpServers": {
    "serumv1-preset-generator": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/biogin/serumv1-preset-generator@v1.0.0",
               "serum-gen-mcp"]
    }
  }
}
```

Or hand the whole thing to an assistant with file/terminal access on the
target machine:

```
Please set up the serumv1-preset-generator MCP server on this computer.

1. Install `uv` (a Python package manager) if it isn't already installed --
   on Mac/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   on Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

2. Register it as an MCP server pointed at
   https://github.com/biogin/serumv1-preset-generator (no need to clone it
   yourself -- `uv` fetches and builds it). If I'm on Claude Code, run:
   `claude mcp add serumv1-preset-generator -- uvx --from git+https://github.com/biogin/serumv1-preset-generator@v1.0.0 serum-gen-mcp`
   If I'm on Claude Desktop, add this to claude_desktop_config.json
   (Settings -> Developer -> Edit Config):
   {"mcpServers": {"serumv1-preset-generator": {"command": "uvx", "args":
   ["--from", "git+https://github.com/biogin/serumv1-preset-generator@v1.0.0",
   "serum-gen-mcp"]}}}

3. Tell me exactly what you did, then tell me to fully quit and restart my
   chat app (not just close the window) for it to take effect.
```

For development, or to configure beyond the defaults (`SERUM_GEN_SERUM_ROOT`,
a custom Init template, etc. — see Configuration below):

```sh
git clone https://github.com/biogin/serumv1-preset-generator
cd serumv1-preset-generator
uv sync
claude mcp add serumv1-preset-generator --scope user -- \
  /opt/homebrew/bin/uv --directory "$(pwd)" run serum-gen-mcp
```

Use an absolute path for `uv` (Claude Desktop doesn't start servers with your
shell's `PATH`) — replace `/opt/homebrew/bin/uv` with the output of `which uv`.

### Architecture

No model call and no API key live anywhere in this codebase ([ADR
0004](docs/adr/0004-no-model-in-the-server.md)): the calling MCP client
designs the sound; this project only validates it against the Parameter
Reference and writes the `.fxp` bytes.

### Tools

| Tool | Description |
|---|---|
| `write_patch(patch, constraints=[])` | Write a new preset from settings you designed. Returns a Patch Summary (the exact values written) and the Preset's path. |
| `edit_patch(preset, changes, constraints=[])` | Apply a partial change to an existing preset as a new Revision (`<name>_v2`, …); the original is never touched. Returns the Patch Summary plus every resulting difference. |
| `list_parameters()` | The full Parameter Reference: every settable name, its range/options and Init value, plus valid modulation sources/destinations and factory wavetables. |
| `describe_preset(preset)` | A human-readable summary of an existing preset's current settings and modulation matrix. |

You don't call these by hand — the chat app builds them from your request,
guided by this server's own instructions and `list_parameters()`.

### Command line

```sh
uv run serum-gen inspect path/to/preset.fxp   # every parameter and Routing of a preset
```

That's the only CLI command: designing or revising a preset from a description
needs a model, and there's no model in this codebase — so there's nothing for
a bare terminal command to call.

### Configuration

All settings are optional, set in the environment or `.env`:

| Variable | Default |
|---|---|
| `SERUM_GEN_OUTPUT_DIR` | Serum's `Presets/User/AI` |
| `SERUM_GEN_SERUM_ROOT` | `/Library/Audio/Presets/Xfer Records/Serum Presets` |
| `SERUM_GEN_TEMPLATE` | the packaged Init preset |

Developed and tested on macOS; Windows and Linux likely work too via
`SERUM_GEN_SERUM_ROOT` but are untested — there's no macOS-specific code
anywhere in this project.

### Known limitations

- `edit_patch` has worked well on presets like "Biggest Hard 808" + "hit
  harder," but at least one case ("PR 808 Kick Circuit [SD]" + "hit harder")
  didn't clearly change the sound as asked, in testing before this project
  dropped its own model. Treat a Revision as a starting point to audition,
  not a guaranteed result.
- Result quality tracks whatever chat app and model you're using — this
  server has no sound-design opinion of its own.

### Development

```sh
uv run pytest        # no API key or network needed anywhere in this suite
uv run mypy          # strict
uv run ruff check && uv run ruff format --check
```

Tests that read the factory library skip when Serum isn't installed.

### Prior art

[serum-mcp](https://github.com/Celian-mrc/serum-mcp) does the same thing for
**Serum 2**, whose `.SerumPreset` format Xfer doesn't publish (its own docs
note parameters are shipped with confidence levels, not certainty). This
project targets **Serum 1**'s `.fxp` format instead, verified byte-for-byte
against the installed factory library — a different synth version, not a
better approach to the same one.

### Design notes

[`CONTEXT.md`](CONTEXT.md) (glossary) and [`docs/adr/`](docs/adr/) (decisions).

### License

[MIT](LICENSE)
