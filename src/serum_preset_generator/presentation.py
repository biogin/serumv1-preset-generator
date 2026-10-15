"""How a DesignResult and a Patch read to the caller — the CLI and the MCP tools share this."""

from collections.abc import Collection

from . import fxp
from .constraints import label
from .design import DesignResult
from .parameter_reference import DESIGNABLE_MOD_SOURCES, MOD_DESTINATIONS, parameters_by_module
from .patch import Patch
from .resources import default_template


def success_text(result: DesignResult) -> str:
    assert result.preset_path is not None  # a passed validation always writes one
    lines = list(result.summary)
    if result.changes:
        lines += ["", "Changes:", *(f"- {change}" for change in result.changes)]
    if result.validation.constraints:
        kept = ", ".join(
            f"{label(name)} {'✓' if ok else '✗'}"
            for name, ok in result.validation.constraints.items()
        )
        lines += ["", f"Constraints: {kept}"]
    lines += [
        "",
        f"Preset: {result.preset_path}",
        f"In Serum's browser: User → {result.preset_path.parent.name} (shows up right away)",
    ]
    return "\n".join(lines)


def failure_text(result: DesignResult) -> str:
    lines = ["Invalid patch:"]
    lines += [f"  - {e}" for e in result.validation.errors]
    broken = [label(n) for n, ok in result.validation.constraints.items() if not ok]
    if broken:
        lines.append(f"Constraints broken: {', '.join(broken)}")
    return "\n".join(lines)


def describe_patch(patch: Patch) -> str:
    """Every parameter and Routing of an existing Patch, as Serum would show it."""
    lines = [
        patch.name,
        f"  Osc A wavetable: {patch.wavetable_a or '(default)'}",
        f"  Osc B wavetable: {patch.wavetable_b or '(default)'}",
    ]
    for module, params in parameters_by_module().items():
        lines.append(f"\n{module}")
        for param in params:
            lines.append(f"  {param.name}: {param.format(patch.params[param.name])}")
    lines.append("\nModulation matrix")
    for routing in patch.routings or []:
        lines.append(f"  {routing.slot}: {routing}")
    if not patch.routings:
        lines.append("  (none)")
    return "\n".join(lines)


def parameter_reference_text(wavetables: Collection[str] | None = None) -> str:
    """The full Parameter Reference: every settable name, its range/options and Init

    value, plus valid modulation sources/destinations and (if known) factory
    wavetables. What `list_parameters()` returns.
    """
    init = fxp.read(default_template())
    sections = []
    for module, params in parameters_by_module().items():
        designable = [p for p in params if p.designable]
        if designable:
            lines = [f"{module}:"] + [
                f"- {p.name}: {p.describe()} (Init: {p.format(init.params[p.name])})"
                for p in designable
            ]
            sections.append("\n".join(lines))
    sections.append("Modulation sources: " + ", ".join(DESIGNABLE_MOD_SOURCES))
    sections.append("Modulation destinations: " + ", ".join(MOD_DESTINATIONS))
    sections.append(
        ("Factory wavetables:\n" + "\n".join(sorted(wavetables)))
        if wavetables
        else "Factory wavetables: (unknown; omit wavetable_a/wavetable_b to use Serum's default)"
    )
    return "\n\n".join(sections)
