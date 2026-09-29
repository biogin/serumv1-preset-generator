"""Constraint checks at the pipeline seam: the model must honour what the description demands."""

from dataclasses import replace

import pytest
from fake_model import ScriptedModel
from test_design_patch import brief, valid_draft

from serum_preset_generator import fxp
from serum_preset_generator.parameter_reference import PARAMETERS_BY_NAME
from serum_preset_generator.pipeline import ParameterValue, RoutingDraft, design_patch


def v(**settings):
    """ParameterValues from keyword names: _ stands for a space, or for > in OscS_Fil,
    or is a real underscore (Dist_Drv). Unknown names fail loudly."""

    def name(key):
        spellings = (key.replace("_", " "), key.replace("_Fil", ">Fil").replace("_", " "), key)
        return next(n for n in spellings if n in PARAMETERS_BY_NAME)

    return [ParameterValue(name=name(k), value=value) for k, value in settings.items()]


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
def test_a_draft_breaking_a_constraint_is_retried_until_it_holds(config, constraint):
    breaking, keeping = CASES[constraint]
    model = ScriptedModel(
        [brief(constraints=[constraint]), valid_draft(values=breaking), valid_draft(values=keeping)]
    )

    result = design_patch("bass", model=model, config=config)

    assert result.validation.passed
    assert result.validation.retries == 1
    assert result.validation.constraints == {constraint: True}
    assert constraint.replace("_", " ") in model.prompts[-1]  # the model was told why


def test_a_constraint_that_never_holds_writes_nothing_and_says_why(config):
    breaking, _ = CASES["clean_sub"]
    model = ScriptedModel([brief(constraints=["clean_sub"])] + [valid_draft(values=breaking)] * 2)

    result = design_patch("bass", model=model, config=replace(config, max_retries=1))

    assert result.preset_path is None
    assert result.validation.constraints == {"clean_sub": False}
    assert any("clean sub" in e and "Distortion" in e for e in result.validation.errors)


def test_every_constraint_is_reported(config):
    model = ScriptedModel(
        [brief(constraints=["no_reverb", "mono"]), valid_draft(values=v(Rev_Enable="Off"))]
    )

    result = design_patch("pad", model=model, config=config)

    assert result.validation.constraints == {"no_reverb": True, "mono": True}


def test_checks_see_init_values_the_draft_leaves_alone(config):
    # Init has Osc S off, so an untouched sub can't be dirty; but Init also has
    # the filter drive at 0, so switching the sub into a driven filter breaks it.
    dirty = v(Osc_S_On="On", Filter_On="On", OscS_Fil="On", Fil_Driv=50.0)
    model = ScriptedModel([brief(constraints=["clean_sub"]), valid_draft(values=dirty),
                           valid_draft(values=[])])  # fmt: skip

    result = design_patch("bass", model=model, config=config)

    assert result.validation.retries == 1
    assert fxp.read(result.preset_path.read_bytes()).params["Osc S On"] == "Off"


def r(source, destination, amount=50.0):
    return RoutingDraft(source=source, destination=destination, amount=amount)


# Drafts that break a constraint in less obvious ways; each must be sent back.
SUBTLE_BREAKS = [
    ("clean_sub", v(FX_Fil_Enable="On", FX_Fil_Type="Scream LP"), []),
    ("clean_sub", v(Osc_S_On="On", Filter_On="On", OscS_Fil="On"), [r("LFO 1", "Fil Driv")]),
    ("no_distortion", v(FX_Fil_Enable="On", FX_Fil_Drive=30.0), []),
    ("no_reverb", v(Filter_On="On", Fil_Type="Reverb"), []),
    ("no_reverb", v(FX_Fil_Enable="On", FX_Fil_Type="Reverb"), []),
    ("mono", v(Dly_Enable="On", Dly_TimL="1/8", Dly_TimR="1/4"), []),
    ("mono", v(Filter_On="On", Fil_Stereo=70.0), []),
    ("mono", v(FX_Fil_Enable="On", FX_Fil_Pan=80.0), []),
    ("mono", v(), [r("LFO 1", "A Pan")]),
]


@pytest.mark.parametrize(("constraint", "values", "routings"), SUBTLE_BREAKS)
def test_subtle_breaks_are_caught(config, constraint, values, routings):
    draft = valid_draft(values=values, routings=routings)
    model = ScriptedModel([brief(constraints=[constraint]), draft])

    result = design_patch("x", model=model, config=replace(config, max_retries=0))

    assert result.validation.constraints == {constraint: False}


def test_a_stereo_effect_at_zero_mix_is_still_mono(config):
    draft = valid_draft(values=v(Cho_Enable="On", Cho_Wet=0.0, Hyp_Enable="On", Hyp_Wet=0.0))
    model = ScriptedModel([brief(constraints=["mono"]), draft])

    result = design_patch("x", model=model, config=config)

    assert result.validation.constraints == {"mono": True}


def test_constraints_are_not_reported_when_the_draft_failed_for_other_reasons(config):
    bad = valid_draft(values=[ParameterValue(name="Nope", value=1.0)])
    model = ScriptedModel([brief(constraints=["mono"]), bad])

    result = design_patch("x", model=model, config=replace(config, max_retries=0))

    assert result.validation.constraints == {}
