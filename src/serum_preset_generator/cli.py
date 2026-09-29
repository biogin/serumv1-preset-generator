import argparse
import sys
from pathlib import Path

from . import fxp
from .parameter_reference import PARAMETERS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="serum-gen")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="print a Serum 1 preset's parameters")
    inspect.add_argument("preset", type=Path)
    args = parser.parse_args(argv)

    return _inspect(args.preset)


def _inspect(path: Path) -> int:
    try:
        patch = fxp.read(path.read_bytes())
    except (OSError, fxp.FxpError) as e:
        print(f"serum-gen: {path}: {e}", file=sys.stderr)
        return 1

    print(patch.name)
    for param in PARAMETERS:
        value = patch.params[param.name]
        shown = value if isinstance(value, str) else f"{value:.1f} {param.unit}".rstrip()
        print(f"  {param.name}: {shown}")
    print(f"  Osc A wavetable: {patch.wavetable_a or '(default)'}")
    print(f"  Osc B wavetable: {patch.wavetable_b or '(default)'}")
    return 0
