"""`serum-gen inspect <preset>` reads a Serum 1 preset's settings and mod matrix.

Designing or revising a preset from a description happens through the MCP
server (see README): there's no model in this codebase to do that from a bare
terminal (ADR 0004).
"""

import sys
from pathlib import Path

from . import fxp
from .presentation import describe_patch


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] != "inspect":
        print("usage: serum-gen inspect <preset.fxp>", file=sys.stderr)
        return 1
    return _inspect(Path(args[1]))


def _inspect(path: Path) -> int:
    try:
        patch = fxp.read(path.read_bytes())
    except (OSError, fxp.FxpError) as e:
        print(f"serum-gen: {path}: {e}", file=sys.stderr)
        return 1
    print(describe_patch(patch))
    return 0
