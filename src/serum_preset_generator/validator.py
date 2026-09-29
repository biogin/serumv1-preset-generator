"""Checks a draft Patch against the Parameter Reference. Pure code, no LLM."""

from collections.abc import Collection

from .parameter_reference import PARAMETERS_BY_NAME
from .patch import Patch


def validate(patch: Patch, wavetables: Collection[str] | None = None) -> list[str]:
    """Return human-readable errors; an empty list means Serum can hold this Patch.

    `wavetables` lists the table paths Serum can load; None skips that check.
    """
    errors = []
    for name, value in patch.params.items():
        param = PARAMETERS_BY_NAME.get(name)
        if param is None:
            errors.append(f"{name!r} is not a Serum parameter in the Parameter Reference")
        elif not param.designable:
            errors.append(f"{name} can't be set by the model; leave it at Init")
        elif problem := param.check(value):
            errors.append(problem)
    if wavetables is not None:
        for slot, table in (("Osc A", patch.wavetable_a), ("Osc B", patch.wavetable_b)):
            if table is not None and table not in wavetables:
                errors.append(f"{slot} wavetable {table!r} is not a factory wavetable")
    return errors
