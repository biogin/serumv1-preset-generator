"""`serum-gen "<sound description>"` designs a Preset; `serum-gen inspect <preset>` reads one."""

import argparse
import logging
import sys
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from . import fxp
from .parameter_reference import parameters_by_module
from .pipeline import DesignConfig, design_patch


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
    if model is None or config is None:
        # Imported lazily: loading it reads .env and builds the Anthropic client.
        from .config import load_design_config, load_environment, make_model

        load_environment()
        model = model or make_model()
        config = config or load_design_config()

    result = design_patch(description, model=model, config=config)
    if not result.validation.passed:
        print(
            f"serum-gen: no valid patch after {result.validation.retries} retries:",
            *(f"  - {e}" for e in result.validation.errors),
            sep="\n",
            file=sys.stderr,
        )
        return 1

    assert result.preset_path is not None  # a passed validation always writes one
    print(result.recipe)
    print(f"\nPreset: {result.preset_path}")
    print(f"In Serum's browser: User / {result.preset_path.parent.name} ({result.model})")
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
    return 0
