"""Validates and writes a Patch (ADR 0004). No model calls here: the calling

MCP client designs the sound; this module only checks it against the
Parameter Reference and Constraints, then writes the `.fxp` bytes. The same
functions make a Revision: `edit_patch` starts from an existing Preset
instead of Init and takes only the changes.
"""

import re
import unicodedata
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from itertools import chain, count
from pathlib import Path

from . import fxp
from .constraints import Constraint
from .constraints import check as check_constraint
from .parameter_reference import parameters_by_module
from .patch import Patch, Routing
from .validator import validate

PRESET_NAME_LIMIT = 31  # Serum stores up to 31 characters


@dataclass(frozen=True)
class DesignConfig:
    output_dir: Path
    template: bytes
    wavetables: frozenset[str] | None = None  # None: don't check wavetable names


@dataclass
class ValidationReport:
    passed: bool
    errors: list[str] = field(default_factory=list)
    # Each constraint asked for, and whether the written Patch keeps it. Empty
    # when validation failed before constraints could be checked.
    constraints: dict[Constraint, bool] = field(default_factory=dict)


@dataclass
class DesignResult:
    # The Patch Summary: "name: value" lines for what was explicitly set, in
    # Parameter Reference order. Empty when validation failed.
    summary: list[str]
    preset_path: Path | None
    validation: ValidationReport
    # For a Revision: each difference as "name: old → new", worked out by code.
    changes: list[str] = field(default_factory=list)


def write_patch(
    patch: Patch, *, constraints: Sequence[Constraint] = (), config: DesignConfig
) -> DesignResult:
    """Write a new Preset: `patch` applied onto Serum's Init values."""
    current = fxp.read(config.template)
    return _design(
        changes=patch,
        current=current,
        base=config.template,
        constraints=constraints,
        config=config,
        keep_unset=False,
        output_name=_safe_name(patch.name),
        suffixes=chain([""], (f"_{n}" for n in count(2))),
    )


def edit_patch(
    preset: Path, changes: Patch, *, constraints: Sequence[Constraint] = (), config: DesignConfig
) -> DesignResult:
    """A Revision of `preset`: `changes` applied on top; `preset` itself is untouched."""
    base = preset.read_bytes()
    current = fxp.read(base)
    stem = re.sub(r"_v\d+$", "", preset.stem)
    routings_locked = not fxp.routings_writable(base)
    locked_parameters = frozenset(current.params) - fxp.writable_parameters(base)
    result = _design(
        changes=changes,
        current=current,
        base=base,
        constraints=constraints,
        config=config,
        keep_unset=True,
        output_name=_safe_name(stem),
        suffixes=(f"_v{n}" for n in count(2)),
        routings_locked=routings_locked,
        locked_parameters=locked_parameters,
    )
    if result.preset_path is not None:
        after = fxp.read(result.preset_path.read_bytes())
        result = replace(result, changes=_changes(current, after))
    return result


def _design(
    *,
    changes: Patch,
    current: Patch,
    base: bytes,
    constraints: Sequence[Constraint],
    config: DesignConfig,
    keep_unset: bool,
    output_name: str,
    suffixes: Iterator[str],
    routings_locked: bool = False,
    locked_parameters: frozenset[str] = frozenset(),
) -> DesignResult:
    whole = _whole(current, changes, keep_unset)
    errors = validate(changes, config.wavetables)
    errors += [
        f"{name}: this Preset was saved by an older Serum build, which doesn't store "
        f"{name}. Leave it out"
        for name in changes.params
        if name in locked_parameters
    ]
    if routings_locked and changes.routings is not None and changes.routings != current.routings:
        errors.append(
            "routings: this Preset was saved by an older Serum build, so its modulation "
            "matrix can't be rewritten. Leave routings unset and change only parameter values"
        )
    results: dict[Constraint, bool] = {}
    if not errors:  # constraints only make sense for a Patch Serum can hold
        for constraint in constraints:
            problems = check_constraint(constraint, whole)
            results[constraint] = not problems
            errors += problems
    if errors:
        return DesignResult(
            summary=[], preset_path=None, validation=ValidationReport(False, errors, results)
        )
    to_write = _to_write(changes, whole, keep_unset)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    path = _write_new_preset(
        config.output_dir,
        output_name,
        suffixes,
        lambda name: fxp.write(replace(to_write, name=name), base=base),
    )
    return DesignResult(
        summary=_summary(changes),
        preset_path=path,
        validation=ValidationReport(True, [], results),
    )


def _whole(current: Patch, changes: Patch, keep_unset: bool) -> Patch:
    """The Patch as Serum will load it: `current`/Init with `changes` applied."""
    return Patch(
        name=changes.name or current.name,
        params={**current.params, **changes.params},
        wavetable_a=changes.wavetable_a or (current.wavetable_a if keep_unset else None),
        wavetable_b=changes.wavetable_b or (current.wavetable_b if keep_unset else None),
        routings=(
            changes.routings
            if changes.routings is not None
            else (current.routings if keep_unset else [])
        ),
    )


def _to_write(changes: Patch, whole: Patch, keep_unset: bool) -> Patch:
    """What to hand the codec: `changes`, with wavetables and matrix resolved."""
    routings = changes.routings if changes.routings is not None else (None if keep_unset else [])
    return replace(changes, wavetable_a=whole.wavetable_a, wavetable_b=whole.wavetable_b,
                   routings=routings)  # fmt: skip


def _summary(changes: Patch) -> list[str]:
    """`changes`, as "name: value" lines in Parameter Reference order."""
    lines = []
    for module_params in parameters_by_module().values():
        for p in module_params:
            if p.name in changes.params:
                lines.append(f"{p.name}: {p.format(changes.params[p.name])}")
    if changes.wavetable_a:
        lines.append(f"Osc A wavetable: {changes.wavetable_a}")
    if changes.wavetable_b:
        lines.append(f"Osc B wavetable: {changes.wavetable_b}")
    for routing in changes.routings or []:
        lines.append(f"Routing: {routing}")
    return lines


def _changes(before: Patch, after: Patch) -> list[str]:
    """Each difference as "name: old → new", in Parameter Reference order."""
    lines = []
    for module_params in parameters_by_module().values():
        for p in module_params:
            if not p.designable:  # e.g. "Mod 1 amt", which mirrors a Routing listed below
                continue
            old, new = before.params[p.name], after.params[p.name]
            if old != new and not (
                isinstance(old, float) and isinstance(new, float) and abs(old - new) < 1e-4
            ):
                lines.append(f"{p.name}: {p.format(old)} → {p.format(new)}")
    for osc, old_table, new_table in (
        ("Osc A wavetable", before.wavetable_a, after.wavetable_a),
        ("Osc B wavetable", before.wavetable_b, after.wavetable_b),
    ):
        if old_table != new_table:
            lines.append(f"{osc}: {old_table or '(default)'} → {new_table or '(default)'}")
    old_routings, new_routings = before.routings or [], after.routings or []
    for slot in range(1, max(len(old_routings), len(new_routings)) + 1):
        old_r = old_routings[slot - 1] if slot <= len(old_routings) else None
        new_r = new_routings[slot - 1] if slot <= len(new_routings) else None
        if old_r == new_r:
            continue
        if (
            old_r
            and new_r
            and (old_r.source, old_r.destination) == (new_r.source, new_r.destination)
        ):
            lines.append(
                f"Routing {slot}: {old_r.source} → {old_r.destination} "
                f"{old_r.amount:g} % → {new_r.amount:g} %"
            )
        else:
            lines.append(f"Routing {slot}: {_routing_text(old_r)} → {_routing_text(new_r)}")
    return lines


def _routing_text(routing: Routing | None) -> str:
    return "(empty)" if routing is None else str(routing)


def _safe_name(proposed: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", proposed).encode("ascii", "ignore").decode()
    ascii_name = ascii_name.replace("/", "-")  # "1/8" stays readable as "1-8"
    cleaned = re.sub(r"[^A-Za-z0-9 _\-()\[\]]+", "", ascii_name).strip()
    return cleaned[:PRESET_NAME_LIMIT].strip() or "AI Patch"


def _write_new_preset(
    directory: Path, name: str, suffixes: Iterator[str], render: Callable[[str], bytes]
) -> Path:
    """Write the Preset as `name` + the first suffix whose file is free; never overwrite.

    Names are trimmed so name plus suffix still fits Serum's limit. Files are
    created exclusively, so a file appearing between check and write is skipped.
    """
    for suffix in suffixes:
        stem = name[: PRESET_NAME_LIMIT - len(suffix)].rstrip() + suffix
        path = directory / f"{stem}.fxp"
        if path.exists():
            continue
        data = render(stem)  # before creating the file: a failed render leaves nothing
        try:
            with path.open("xb") as f:
                f.write(data)
            return path
        except FileExistsError:
            continue
    raise AssertionError("suffixes are endless")
