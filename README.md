# Serum Preset Generator

Describe a sound in plain language ("aggressive cyberpunk bass that keeps the sub
clean", or in Russian). You get a step-by-step **Patch Recipe** and a ready-to-load
**Preset** in Xfer Serum 1's browser (`User → AI`).

- **Pipeline:** a LangGraph pipeline goes plan → draft → validate → retry → write, on Claude Sonnet 5.5.
- **Validation:** every draft is checked by code against a **Parameter Reference** of all 299 Serum 1 parameters and against the **Constraints** the description states (clean sub, no reverb, no distortion, mono). Failures go back to the model with concrete fixes.
- **Preset files:** Serum 1's `.fxp` format is written by a codec built for this project and tested byte-for-byte against the factory library.
- **Interfaces:** it runs from the command line, or as an **MCP server** you chat with from any MCP-compatible client (Claude Desktop, Claude Code, and others).

Design notes: [`CONTEXT.md`](CONTEXT.md) (glossary) and [`docs/adr/`](docs/adr/) (decisions).

## Setup

Requires Serum 1 installed, Python 3.12 and [`uv`](https://docs.astral.sh/uv/), and your
own Anthropic API key (usage is billed to that key at [Anthropic's published
rates](https://www.anthropic.com/pricing)). Developed and tested on macOS; Windows and
Linux likely work too via `SERUM_GEN_SERUM_ROOT` (see Configuration below) but are
untested.

**Quick try**, no clone needed:

```sh
ANTHROPIC_API_KEY=sk-ant-… uvx --from git+https://github.com/biogin/serum-preset-generator@v0.1.0 \
  serum-gen "warm evolving pad, no reverb"
```

**Full setup** — clone this repo first if you want to configure `SERUM_GEN_SERUM_ROOT`,
a custom template, or anything else in Configuration below via a `.env` file instead of
exported env vars:

```sh
uv sync
echo 'ANTHROPIC_API_KEY=sk-ant-…' > .env && chmod 600 .env   # never committed
```

## Command line

```sh
uv run serum-gen "dubstep wobble bass, the filter wobbles at 1/8"
uv run serum-gen -v "тёмный мягкий пэд"          # -v traces each pipeline step
uv run serum-gen revise "808 Boom" "hit harder"  # a Revision: new "808 Boom_v2", original untouched
uv run serum-gen inspect path/to/preset.fxp      # every parameter and Routing of a preset
```

`revise` takes a preset name, searched in Serum's library (a unique partial name works; if
several match, it lists them), or a path. The Revision's recipe lists only what changed and
why. Presets saved by older Serum builds (all factory presets) can have their knobs and
switches revised but not their modulation matrix.

## MCP server (any MCP-compatible client)

The server exposes two tools: `design_patch(sound_description)` and
`revise_patch(preset, feedback)`.

### Quick try, no clone needed

**Claude Code:**

```sh
claude mcp add serum-gen --scope user -e ANTHROPIC_API_KEY=sk-ant-… -- \
  uvx --from git+https://github.com/biogin/serum-preset-generator@v0.1.0 serum-gen-mcp
```

**Claude Desktop:** in *Settings → Developer → Edit Config*
(`~/Library/Application Support/Claude/claude_desktop_config.json`), add the following
and restart Claude Desktop:

```json
{
  "mcpServers": {
    "serum-gen": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/biogin/serum-preset-generator@v0.1.0",
               "serum-gen-mcp"],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-…" }
    }
  }
}
```

### Full setup, for configuration beyond the defaults

Clone the repo and use `.env` (as in Setup above) if you want `SERUM_GEN_SERUM_ROOT`,
a custom template, or other Configuration settings without passing env vars by hand.

**Claude Code:**

```sh
claude mcp add serum-gen --scope user -- \
  /opt/homebrew/bin/uv --directory ~/PersonalProjects/serum-preset-generator run serum-gen-mcp
```

**Claude Desktop:**

```json
{
  "mcpServers": {
    "serum-gen": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["--directory", "/Users/<you>/PersonalProjects/serum-preset-generator",
               "run", "serum-gen-mcp"]
    }
  }
}
```

It reads `.env` from that folder, so the key needn't be in the client's environment.
Use absolute paths: Claude Desktop doesn't start servers with your shell's `PATH`.
Replace `/opt/homebrew/bin/uv` with the output of `which uv` if yours lives elsewhere,
and the folder with wherever you cloned this repo.

---

Either way, then ask it, for example: *"Make me a Serum preset: warm evolving pad, no
reverb"*, or *"Make my Biggest Hard 808 preset hit harder."*

## Configuration

All settings are optional, set in the environment or `.env`:

| Variable | Default |
|---|---|
| `SERUM_GEN_PROVIDER` | `anthropic` (a local `ollama` option is planned) |
| `SERUM_GEN_MODEL` | `claude-sonnet-5-5` |
| `SERUM_GEN_EFFORT` | `medium` |
| `SERUM_GEN_OUTPUT_DIR` | Serum's `Presets/User/AI` |
| `SERUM_GEN_SERUM_ROOT` | `/Library/Audio/Presets/Xfer Records/Serum Presets` |
| `SERUM_GEN_TEMPLATE` | the packaged Init preset |
| `SERUM_GEN_MAX_RETRIES` | `3` |

## Known limitations

- **Cloud only.** Every call costs real Anthropic API usage on your own key; there's no
  free or offline local-model path yet (tracked as a future option).
- **Revision quality is unverified on some cases.** `revise_patch` has worked well on
  presets like "Biggest Hard 808" + "hit harder," but at least one case ("PR 808 Kick
  Circuit [SD]" + "hit harder") didn't clearly change the sound as asked. Treat
  Revisions as a starting point to audition, not a guaranteed result.

## Development

```sh
uv run pytest        # tests use a scripted fake model: no API key or network needed
uv run mypy          # strict
uv run ruff check && uv run ruff format --check
```

Tests that read the factory library skip when Serum isn't installed.
