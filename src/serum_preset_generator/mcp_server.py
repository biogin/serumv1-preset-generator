"""MCP server: `design_patch` for Claude Desktop / Claude Code (ADR 0002).

A thin wrapper over the same pipeline as the CLI. It talks MCP over stdio, so
nothing here may print to stdout; logs go to stderr.
"""

import logging

from langchain_core.language_models import BaseChatModel
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .config import resolve
from .pipeline import DesignConfig, design_patch
from .presentation import failure_text, success_text

log = logging.getLogger(__name__)

INSTRUCTIONS = """\
Designs Xfer Serum 1 presets from a description of a sound. Call design_patch
with the producer's Sound Description in their own words and language. It
returns a Patch Recipe and writes a Preset into Serum's User/AI folder. Show the
recipe to the producer; answer follow-up questions about it yourself."""


def build_server(
    model: BaseChatModel | None = None, config: DesignConfig | None = None
) -> MCPServer:
    """The server; `model` and `config` default to the environment's (like the CLI)."""
    server = MCPServer("serum-preset-generator", instructions=INSTRUCTIONS)

    @server.tool(name="design_patch")
    def design_patch_tool(sound_description: str) -> str:
        """Design a Serum 1 preset from a Sound Description.

        Returns a step-by-step Patch Recipe and the path of the Preset written
        into Serum's preset browser (User → AI). Takes about 15-30 seconds.

        Args:
            sound_description: The sound in the producer's words, in English or
                Russian, e.g. "aggressive cyberpunk bass that keeps the sub clean".
        """
        nonlocal model, config
        try:
            model, config = resolve(model, config)
            result = design_patch(sound_description, model=model, config=config)
        except Exception as e:
            # Setup, API and file errors: the chat needs the reason to explain it.
            log.exception("design_patch failed")
            raise ToolError(f"design_patch failed: {type(e).__name__}: {e}") from e
        if not result.validation.passed:
            raise ToolError(failure_text(result))
        return success_text(result)

    return server


def main() -> None:
    build_server().run("stdio")
