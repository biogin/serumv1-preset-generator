"""Checks a draft Patch against the Parameter Reference. Pure code, no LLM."""

from collections.abc import Collection

from .parameter_reference import PARAMETERS_BY_NAME, Scale
from .patch import Patch


def validate(patch: Patch, wavetables: Collection[str] | None = None) -> list[str]:
    """Return human-readable errors; an empty list means Serum can hold this Patch.

    `wavetables` lists the table paths Serum can load; None skips that check.
    """
    errors = []
    for name, value in patch.params.items():
        param = PARAMETERS_BY_NAME.get(name)
        if param is None:
            errors.append(f"{name!r} is not a Serum parameter; use one of {_names()}")
        elif param.scale is Scale.OPTIONS:
            if value not in param.options:
                errors.append(f"{name}: {value!r} is not one of Serum's options for it")
        elif isinstance(value, str):
            errors.append(f"{name}: expected a number in {param.unit or 'units'}, got {value!r}")
        elif not param.minimum <= value <= param.maximum:
            errors.append(
                f"{name}: {value:g} is outside {param.minimum:g}..{param.maximum:g} {param.unit}"
            )
    if wavetables is not None:
        for slot, table in (("Osc A", patch.wavetable_a), ("Osc B", patch.wavetable_b)):
            if table is not None and table not in wavetables:
                errors.append(f"{slot} wavetable {table!r} is not a factory wavetable")
    return errors


def _names() -> str:
    return ", ".join(sorted(PARAMETERS_BY_NAME))
