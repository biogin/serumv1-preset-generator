"""How a DesignResult reads to the producer, the same in the CLI and the MCP tool."""

from .constraints import label
from .pipeline import DesignResult


def success_text(result: DesignResult) -> str:
    assert result.preset_path is not None  # a passed validation always writes one
    lines = [result.recipe or ""]
    if result.validation.constraints:
        kept = ", ".join(
            f"{label(name)} {'✓' if ok else '✗'}"
            for name, ok in result.validation.constraints.items()
        )
        lines += ["", f"Constraints: {kept}"]
    lines += [
        "",
        f"Preset: {result.preset_path}",
        f"In Serum's browser: User → {result.preset_path.parent.name} "
        f"(shows up right away; made by {result.model})",
    ]
    return "\n".join(lines)


def failure_text(result: DesignResult) -> str:
    lines = [f"No valid patch after {result.validation.retries} retries:"]
    lines += [f"  - {e}" for e in result.validation.errors]
    broken = [label(n) for n, ok in result.validation.constraints.items() if not ok]
    if broken:
        lines.append(f"Constraints broken: {', '.join(broken)}")
    return "\n".join(lines)
