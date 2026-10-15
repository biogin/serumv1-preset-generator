"""Constraint checks at the design seam: a Patch must honour what was asked for."""

import pytest

from serum_preset_generator import fxp
from serum_preset_generator.design import write_patch
from serum_preset_generator.parameter_reference import PARAMETERS_BY_NAME
from serum_preset_generator.patch import Patch, Routing


def v(**settings):
    """A params dict from keyword names: _ stands for a space, or for > in OscS_Fil,
    or is a real underscore (Dist_Drv). Unknown names fail loudly."""

    def name(key):
        spellings = (key.replace("_", " "), key.replace("_Fil", ">Fil").replace("_", " "), key)
        return next(n for n in spellings if n in PARAMETERS_BY_NAME)

    return {name(k): value for k, value in settings.items()}


def r(source, destination, amount=50.0):
    return Routing(source, destination, amount)


def patch(**overrides):
    fields = {"name": "x", "routings": None}
    return Patch(**{**fields, **overrides})


CASES = {
    "clean_sub": (
        v(Osc_S_On="On", Dist_Enable="On", Dist_Drv=70.0),
        v(Osc_S_On="On", Filter_On="On", OscS_Fil="Off", Fil_Type="Dist.Comb 1 LP", Fil_Driv=60.0),
    ),
    "no_reverb": (v(Rev_Enable="On"), v(Rev_Enable="Off", Dly_Enable="On")),
    "no_distortion": (v(Filter_On="On", Fil_Driv=40.0), v(Filter_On="On", Fil_Driv=0.0)),
    "mono": (v(A_Pan=20.0), v(A_Pan=0.0, A_Unison=5, A_Uni_LR=0.0)),
}


@pytest.mark.parametrize("constraint", CASES)
def test_a_constraint_is_checked_against_the_whole_patch(config, constraint):
    breaking, keeping = CASES[constraint]

    broken = write_patch(patch(params=breaking), constraints=[constraint], config=config)
    held = write_patch(patch(params=keeping), constraints=[constraint], config=config)

    assert broken.validation.constraints == {constraint: False}
    assert held.validation.constraints == {constraint: True}
    assert constraint.replace("_", " ") in "\n".join(broken.validation.errors)


def test_every_constraint_is_reported(config):
    result = write_patch(
        patch(params=v(Rev_Enable="Off")), constraints=["no_reverb", "mono"], config=config
    )

    assert result.validation.constraints == {"no_reverb": True, "mono": True}


def test_checks_see_init_values_a_patch_leaves_alone(config):
    # Init has Osc S off, so an untouched sub can't be dirty; but Init also has
    # the filter drive at 0, so switching the sub into a driven filter breaks it.
    dirty = v(Osc_S_On="On", Filter_On="On", OscS_Fil="On", Fil_Driv=50.0)

    broken = write_patch(patch(params=dirty), constraints=["clean_sub"], config=config)
    held = write_patch(patch(params={}), constraints=["clean_sub"], config=config)

    assert broken.validation.constraints == {"clean_sub": False}
    assert held.validation.constraints == {"clean_sub": True}
    assert fxp.read(held.preset_path.read_bytes()).params["Osc S On"] == "Off"


@pytest.mark.parametrize(
    ("constraint", "values", "routings"),
    [
        ("clean_sub", v(FX_Fil_Enable="On", FX_Fil_Type="Scream LP"), None),
        ("clean_sub", v(Osc_S_On="On", Filter_On="On", OscS_Fil="On"), [r("LFO 1", "Fil Driv")]),
        ("no_distortion", v(FX_Fil_Enable="On", FX_Fil_Drive=30.0), None),
        ("no_reverb", v(Filter_On="On", Fil_Type="Reverb"), None),
        ("no_reverb", v(FX_Fil_Enable="On", FX_Fil_Type="Reverb"), None),
        ("mono", v(Dly_Enable="On", Dly_TimL="1/8", Dly_TimR="1/4"), None),
        ("mono", v(Filter_On="On", Fil_Stereo=70.0), None),
        ("mono", v(FX_Fil_Enable="On", FX_Fil_Pan=80.0), None),
        ("mono", v(), [r("LFO 1", "A Pan")]),
    ],
)
def test_subtle_breaks_are_caught(config, constraint, values, routings):
    result = write_patch(
        patch(params=values, routings=routings), constraints=[constraint], config=config
    )

    assert result.validation.constraints == {constraint: False}


def test_a_stereo_effect_at_zero_mix_is_still_mono(config):
    result = write_patch(
        patch(params=v(Cho_Enable="On", Cho_Wet=0.0, Hyp_Enable="On", Hyp_Wet=0.0)),
        constraints=["mono"],
        config=config,
    )

    assert result.validation.constraints == {"mono": True}


def test_constraints_are_not_reported_when_the_patch_is_invalid_for_other_reasons(config):
    result = write_patch(patch(params={"Nope": 1.0}), constraints=["mono"], config=config)

    assert result.validation.constraints == {}
