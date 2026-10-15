"""MCP server: `write_patch`/`edit_patch` for any MCP client (ADR 0004).

No model call happens anywhere in this process. The calling client designs
the sound itself, guided by this module's `instructions` and tool
docstrings, and `list_parameters()`/`describe_preset()` for exact facts; this
server only validates the result against the Parameter Reference and
Constraints, then writes the `.fxp` bytes. Nothing here may print to stdout
(MCP talks over stdio); logs go to stderr.
"""

import logging
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from . import fxp
from .config import library_dir, resolve
from .constraints import Constraint
from .design import DesignConfig, edit_patch, write_patch
from .library import AmbiguousPreset, PresetNotFound, find_preset
from .patch import Patch, Routing
from .presentation import describe_patch, failure_text, parameter_reference_text, success_text

log = logging.getLogger(__name__)

INSTRUCTIONS = """\
Validates and writes Xfer Serum 1 presets. You design the sound yourself —
this server has no model of its own (ADR 0004) — then call write_patch with
the exact settings; this process only checks what you send and writes the
file. Call list_parameters() first for exact names, ranges and options:
only parameters it lists can be set; everything else stays at Serum's Init
value (write_patch) or the preset's current value (edit_patch).

A module only sounds when it's switched on: the filter needs "Filter On",
Osc B "Osc B On", the sub oscillator "Osc S On", noise "Osc N On", and each
effect its own "<name> Enable". Route an oscillator through the filter with
its "Osc?>Fil" switch. Movement comes from the modulation matrix (the
`routings` field): a routing sends a source (an LFO, envelope, macro...) to
a destination by an amount from -100 to 100%. An LFO or Env 2/3 does nothing
until it's routed; Env 1 always shapes the volume. Tempo-synced knobs (LFO
rates, delay times) take note values such as "1/4".

To change an existing preset ("make my 808 hit harder"), call describe_preset
to see its current settings, then edit_patch with only the changed values —
everything you don't list keeps its current value. Show the producer what
you set and why, in your own reply; this server returns only the plain
facts (a Patch Summary), never prose explaining them."""


class RoutingInput(BaseModel):
    source: str = Field(description="A modulation source, e.g. 'LFO 1', 'Env 2', 'Macro 1'")
    destination: str = Field(description="A modulation destination; see list_parameters()")
    amount: float = Field(description="-100 to 100 percent")
    bipolar: bool = Field(default=False, description="Modulate around the knob's position")

    def to_routing(self) -> Routing:
        return Routing(self.source, self.destination, self.amount, self.bipolar)


class PatchChanges(BaseModel):
    params: dict[str, float | str] = Field(
        default_factory=dict,
        description="Parameter Reference name -> value (a number in its unit, or an option "
        "name). List only what you're setting; see list_parameters() for valid names/ranges.",
    )
    wavetable_a: str | None = Field(default=None, description="A factory wavetable for Osc A")
    wavetable_b: str | None = Field(default=None, description="A factory wavetable for Osc B")
    routings: list[RoutingInput] | None = Field(
        default=None,
        description="The whole modulation matrix, in slot order (max 32). Omit to leave the "
        "matrix untouched; an empty list clears it.",
    )

    def to_patch(self, name: str = "") -> Patch:
        return Patch(
            name=name,
            params=self.params,
            wavetable_a=self.wavetable_a,
            wavetable_b=self.wavetable_b,
            routings=None if self.routings is None else [r.to_routing() for r in self.routings],
        )


class PatchInput(PatchChanges):
    name: str = Field(description="Preset name as shown in Serum's browser, max 31 characters")


def build_server(config: DesignConfig | None = None, library: Path | None = None) -> MCPServer:
    """The server; `config` defaults to the environment's (like the CLI)."""
    server = MCPServer("serumv1-preset-generator", instructions=INSTRUCTIONS)

    @server.tool(name="write_patch")
    def write_patch_tool(patch: PatchInput, constraints: list[Constraint] | None = None) -> str:
        """Write a new Serum 1 preset from settings you designed.

        Returns a Patch Summary (the exact settings written) and the path of the
        Preset written into Serum's preset browser (User → AI).

        Args:
            patch: The settings to write.
            constraints: Hard requirements to check before writing (e.g. the producer
                said "keep the sub clean" or "no reverb").
        """
        nonlocal config
        try:
            config = resolve(config)
            result = write_patch(
                patch.to_patch(patch.name), constraints=constraints or [], config=config
            )
        except Exception as e:
            log.exception("write_patch failed")
            raise ToolError(f"write_patch failed: {type(e).__name__}: {e}") from e
        if not result.validation.passed:
            raise ToolError(failure_text(result))
        return success_text(result)

    @server.tool(name="edit_patch")
    def edit_patch_tool(
        preset: str, changes: PatchChanges, constraints: list[Constraint] | None = None
    ) -> str:
        """Make a Revision of an existing Serum 1 preset: only the settings you list change.

        Writes a new Preset next to the others in User → AI (named <preset>_v2,
        _v3, ...; the original is never changed, and keeps its name) and returns
        a Patch Summary of what you set plus every resulting difference from the
        original.

        Args:
            preset: The preset's name as shown in Serum's browser (a partial name
                works if it's unique), or a full path to its .fxp file.
            changes: Only the settings to change; everything else keeps its current value.
            constraints: Hard requirements to check before writing.
        """
        nonlocal config
        try:
            path = find_preset(preset, library or library_dir())
        except (PresetNotFound, AmbiguousPreset) as e:
            raise ToolError(str(e)) from e
        try:
            config = resolve(config)
            result = edit_patch(
                path, changes.to_patch(), constraints=constraints or [], config=config
            )
        except Exception as e:
            log.exception("edit_patch failed")
            raise ToolError(f"edit_patch failed: {type(e).__name__}: {e}") from e
        if not result.validation.passed:
            raise ToolError(failure_text(result))
        return success_text(result)

    @server.tool(name="list_parameters")
    def list_parameters_tool() -> str:
        """The full Parameter Reference: every settable name, its range/options and Init

        value, plus valid modulation sources/destinations and factory wavetables.
        Call this whenever you're unsure of an exact name, range or option before
        write_patch/edit_patch.
        """
        nonlocal config
        config = resolve(config)
        return parameter_reference_text(config.wavetables)

    @server.tool(name="describe_preset")
    def describe_preset_tool(preset: str) -> str:
        """A human-readable summary of an existing preset's current settings and mod matrix.

        Args:
            preset: The preset's name as shown in Serum's browser (a partial name
                works if it's unique), or a full path to its .fxp file.
        """
        try:
            path = find_preset(preset, library or library_dir())
        except (PresetNotFound, AmbiguousPreset) as e:
            raise ToolError(str(e)) from e
        return describe_patch(fxp.read(path.read_bytes()))

    return server


def main() -> None:
    build_server().run("stdio")
