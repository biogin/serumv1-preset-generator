"""`serum-gen "<sound description>"` designs a Preset; `serum-gen inspect <preset>` reads one."""

import argparse
import logging
import sys
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from . import fxp
from .parameter_reference import parameters_by_module
from .pipeline import DesignConfig, design_patch
from .presentation import failure_text, success_text


def main(
    argv: list[str] | None = None,
    *,
    model: BaseChatModel | None = None,
    config: DesignConfig | None = None,
) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 2 and args[0] == "inspect" and args[1].lower().endswith(".fxp"):
        parser = argparse.ArgumentParser(prog="serum-gen inspect")
        parser.add_argument("preset", type=Path)
        return _inspect(parser.parse_args(args[1:]).preset)

    parser = argparse.ArgumentParser(
        prog="serum-gen",
        description="Describe a sound; get a Serum 1 Patch Recipe and Preset. "
        "Use `serum-gen inspect <preset>` to read a preset.",
    )
    parser.add_argument("description", nargs="+", help="the Sound Description")
    parser.add_argument("-v", "--verbose", action="store_true", help="log each pipeline step")
    parsed = parser.parse_args(args)
    logging.basicConfig(
        level=logging.INFO if parsed.verbose else logging.WARNING, format="%(name)s: %(message)s"
    )
    return _design(" ".join(parsed.description), model, config)


def _design(description: str, model: BaseChatModel | None, config: DesignConfig | None) -> int:
    # Imported lazily: loading config reads .env and builds the Anthropic client.
    from .config import resolve

    model, config = resolve(model, config)
    result = design_patch(description, model=model, config=config)
    if not result.validation.passed:
        print(f"serum-gen: {failure_text(result)}", file=sys.stderr)
        return 1
    print(success_text(result))
    return 0


def _inspect(path: Path) -> int:
    try:
        patch = fxp.read(path.read_bytes())
    except (OSError, fxp.FxpError) as e:
        print(f"serum-gen: {path}: {e}", file=sys.stderr)
        return 1

    print(patch.name)
    print(f"  Osc A wavetable: {patch.wavetable_a or '(default)'}")
    print(f"  Osc B wavetable: {patch.wavetable_b or '(default)'}")
    for module, params in parameters_by_module().items():
        print(f"\n{module}")
        for param in params:
            print(f"  {param.name}: {param.format(patch.params[param.name])}")
    print("\nModulation matrix")
    for routing in patch.routings or []:
        bipolar = " (bipolar)" if routing.bipolar else ""
        print(
            f"  {routing.slot}: {routing.source} → {routing.destination} "
            f"{routing.amount:.1f} %{bipolar}"
        )
    if not patch.routings:
        print("  (none)")
    return 0
