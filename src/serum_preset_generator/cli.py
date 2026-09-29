"""`serum-gen "<sound description>"` designs a Preset; `serum-gen inspect <preset>` reads one."""

import argparse
import logging
import sys
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from . import fxp
from .library import AmbiguousPreset, PresetNotFound, find_preset
from .parameter_reference import parameters_by_module
from .pipeline import DesignConfig, DesignResult, design_patch, revise_patch
from .presentation import failure_text, success_text


def main(
    argv: list[str] | None = None,
    *,
    model: BaseChatModel | None = None,
    config: DesignConfig | None = None,
    library: Path | None = None,
) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["revise"]:
        parser = argparse.ArgumentParser(
            prog="serum-gen revise", description="Make a Revision of an existing preset."
        )
        parser.add_argument("preset", help="a preset name (searched in Serum's library) or path")
        parser.add_argument("feedback", nargs="+", help="what to change, e.g. 'hit harder'")
        parser.add_argument("-v", "--verbose", action="store_true", help="log each pipeline step")
        parsed = parser.parse_args(args[1:])
        _configure_logging(parsed.verbose)
        return _revise(parsed.preset, " ".join(parsed.feedback), model, config, library)
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
    _configure_logging(parsed.verbose)
    return _design(" ".join(parsed.description), model, config)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING, format="%(name)s: %(message)s"
    )


def _revise(
    query: str,
    feedback: str,
    model: BaseChatModel | None,
    config: DesignConfig | None,
    library: Path | None,
) -> int:
    from .config import library_dir, resolve

    try:
        preset = find_preset(query, library or library_dir())
    except (PresetNotFound, AmbiguousPreset) as e:
        print(f"serum-gen: {e}", file=sys.stderr)
        return 1
    model, config = resolve(model, config)
    return _report(revise_patch(preset, feedback, model=model, config=config))


def _design(description: str, model: BaseChatModel | None, config: DesignConfig | None) -> int:
    # Imported lazily: loading config reads .env and builds the Anthropic client.
    from .config import resolve

    model, config = resolve(model, config)
    return _report(design_patch(description, model=model, config=config))


def _report(result: DesignResult) -> int:
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
        print(f"  {routing.slot}: {routing}")
    if not patch.routings:
        print("  (none)")
    return 0
