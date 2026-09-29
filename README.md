# Serum Preset Generator

Describe a sound in plain language ("aggressive cyberpunk bass that keeps the sub
clean", or in Russian). You get a step-by-step **Patch Recipe** and a ready-to-load
**Preset** in Xfer Serum 1's browser (`User → AI`).

- **Pipeline:** a LangGraph pipeline goes plan → draft → validate → retry → write, on Claude Sonnet 5.5.
- **Validation:** every draft is checked by code against a **Parameter Reference** of all 299 Serum 1 parameters and against the **Constraints** the description states (clean sub, no reverb, no distortion, mono). Failures go back to the model with concrete fixes.
- **Preset files:** Serum 1's `.fxp` format is written by a codec built for this project and tested byte-for-byte against the factory library.
- **Interfaces:** it runs from the command line, or as an **MCP server** you chat with in Claude Desktop or Claude Code.

Design notes: [`CONTEXT.md`](CONTEXT.md) (glossary) and [`docs/adr/`](docs/adr/) (decisions).

## Setup

Requires macOS with Serum 1 installed, Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync
echo 'ANTHROPIC_API_KEY=sk-ant-…' > .env && chmod 600 .env   # never committed
```

## Command line

```sh
uv run serum-gen "dubstep wobble bass, the filter wobbles at 1/8"
uv run serum-gen -v "тёмный мягкий пэд"          # -v traces each pipeline step
uv run serum-gen inspect path/to/preset.fxp      # every parameter and Routing of a preset
```

## MCP server (Claude Desktop / Claude Code)

The server exposes one tool, `design_patch(sound_description)`. It reads `.env`
from this folder, so the key needn't be in the client's environment.

**Claude Code:**

```sh
claude mcp add serum-gen --scope user -- \
  /opt/homebrew/bin/uv --directory ~/PersonalProjects/serum-preset-generator run serum-gen-mcp
```

**Claude Desktop:** in *Settings → Developer → Edit Config*
(`~/Library/Application Support/Claude/claude_desktop_config.json`), add the following
and restart Claude Desktop:

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

Use absolute paths: Claude Desktop doesn't start servers with your shell's `PATH`.
Replace `/opt/homebrew/bin/uv` with the output of `which uv` if yours lives elsewhere,
and the folder with wherever you cloned this repo.
Then ask it, for example: *"Make me a Serum preset: warm evolving pad, no reverb."*

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

## Development

```sh
uv run pytest        # tests use a scripted fake model: no API key or network needed
uv run mypy          # strict
uv run ruff check && uv run ruff format --check
```

Tests that read the factory library skip when Serum isn't installed.
