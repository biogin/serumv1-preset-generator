from dataclasses import replace

import pytest
from fake_model import ScriptedModel

from serum_preset_generator import fxp
from serum_preset_generator.config import default_template
from serum_preset_generator.pipeline import (
    Brief,
    DesignConfig,
    Draft,
    ParameterValue,
    RoutingDraft,
    design_patch,
)


@pytest.fixture
def config(tmp_path):
    return DesignConfig(
        output_dir=tmp_path / "AI",
        template=default_template(),
        max_retries=3,
        wavetables=frozenset({"Analog/PWM Juno.wav", "Digital/Kream.wav"}),
    )


def brief(name="Cyber Bass", language="en"):
    return Brief(category="bass", character="aggressive, overdriven", language=language,
                 preset_name=name)  # fmt: skip


def valid_draft(**overrides):
    fields = {
        "values": [
            ParameterValue(name="Fil Type", value="German LP"),
            ParameterValue(name="Fil Cutoff", value=180.0),
            ParameterValue(name="Fil Reso", value=35.0),
        ],
        "wavetable_a": "Analog/PWM Juno.wav",
        "wavetable_b": None,
        "recipe": "OSC A: PWM Juno. FILTER: German LP at 180 Hz, resonance 35 %.",
    }
    return Draft(**{**fields, **overrides})


def test_a_valid_draft_becomes_a_preset_and_a_recipe(config):
    model = ScriptedModel([brief(), valid_draft()])

    result = design_patch("aggressive cyberpunk bass", model=model, config=config)

    assert result.preset_path == config.output_dir / "Cyber Bass.fxp"
    written = fxp.read(result.preset_path.read_bytes())
    assert written.name == "Cyber Bass"
    assert written.params["Fil Type"] == "German LP"
    assert written.params["Fil Cutoff"] == pytest.approx(180.0, rel=1e-4)
    assert written.params["Fil Reso"] == pytest.approx(35.0, abs=1e-4)
    assert written.wavetable_a == "Analog/PWM Juno.wav"
    assert result.recipe == valid_draft().recipe
    assert result.validation.passed
    assert result.validation.retries == 0


def test_an_invalid_draft_is_retried_with_the_validators_errors(config):
    bad = valid_draft(values=[ParameterValue(name="Fil Cutoff", value=99999.0)])
    model = ScriptedModel([brief(), bad, valid_draft()])

    result = design_patch("aggressive cyberpunk bass", model=model, config=config)

    assert result.validation.passed
    assert result.validation.retries == 1
    assert "Fil Cutoff" in model.prompts[-1] and "99999" in model.prompts[-1]
    assert result.preset_path is not None and result.preset_path.exists()


def test_no_preset_is_written_when_retries_run_out(config):
    bad = valid_draft(wavetable_a="Made Up/Table.wav")
    model = ScriptedModel([brief(), bad, bad, bad, bad])

    result = design_patch("aggressive cyberpunk bass", model=model, config=config)

    assert not result.validation.passed
    assert result.validation.retries == 3
    assert any("Made Up/Table.wav" in e for e in result.validation.errors)
    assert result.preset_path is None
    assert result.recipe is None
    assert not config.output_dir.exists() or not any(config.output_dir.iterdir())


def test_the_model_is_told_which_wavetables_exist(config):
    model = ScriptedModel([brief(), valid_draft()])

    design_patch("aggressive cyberpunk bass", model=model, config=config)

    assert "Digital/Kream.wav" in model.prompts[1]
    assert "Analog/PWM Juno.wav" in model.prompts[1]


def test_an_existing_preset_is_never_overwritten(config):
    first = design_patch("bass", model=ScriptedModel([brief(), valid_draft()]), config=config)
    second = design_patch("bass", model=ScriptedModel([brief(), valid_draft()]), config=config)

    assert first.preset_path == config.output_dir / "Cyber Bass.fxp"
    assert second.preset_path == config.output_dir / "Cyber Bass_2.fxp"
    assert fxp.read(second.preset_path.read_bytes()).name == "Cyber Bass_2"


def test_a_preset_name_serum_cannot_store_is_made_safe(config):
    model = ScriptedModel([brief(name="Кибер/Бас: очень злой и перегруженный"), valid_draft()])

    result = design_patch("кибер бас", model=model, config=config)

    name = result.preset_path.stem
    assert name.isascii() and "/" not in name and len(name) <= 31
    assert fxp.read(result.preset_path.read_bytes()).name == name


def test_the_result_names_the_model_that_actually_answered(config):
    # With refusal fallbacks on, the API may answer with another model.
    model = ScriptedModel([brief(), valid_draft()], served_by="claude-opus-5-5")

    result = design_patch("bass", model=model, config=config)

    assert result.model == "claude-opus-5-5"


def test_numbered_names_still_fit_serums_31_characters(config):
    stem = "A Very Long Preset Name Here"  # 28 characters
    config.output_dir.mkdir(parents=True)
    for n in ["", *(f"_{i}" for i in range(2, 101))]:
        (config.output_dir / f"{stem}{n}.fxp").write_bytes(b"")

    result = design_patch("pad", model=ScriptedModel([brief(stem), valid_draft()]), config=config)

    assert len(result.preset_path.stem) <= 31
    assert fxp.read(result.preset_path.read_bytes()).name == result.preset_path.stem


def test_a_draft_can_use_any_module_in_the_reference(config):
    draft = valid_draft(
        values=[
            ParameterValue(name="A Unison", value=7),
            ParameterValue(name="A UniDet", value=0.3),
            ParameterValue(name="Filter On", value="On"),
            ParameterValue(name="Dist Enable", value="On"),
            ParameterValue(name="Dist_Mode", value="Diode 1"),
            ParameterValue(name="Dist_Drv", value=60.0),
            ParameterValue(name="Env1 Rel", value=0.4),
            ParameterValue(name="Dly_TimL", value="1/8"),
        ]
    )

    result = design_patch("bass", model=ScriptedModel([brief(), draft]), config=config)

    written = fxp.read(result.preset_path.read_bytes()).params
    assert written["A Unison"] == 7
    assert written["A UniDet"] == pytest.approx(0.3, rel=1e-3)
    assert (written["Filter On"], written["Dist Enable"]) == ("On", "On")
    assert written["Dist_Mode"] == "Diode 1"
    assert written["Env1 Rel"] == pytest.approx(0.4, rel=1e-3)
    assert written["Dly_TimL"] == "1/8"


def test_the_model_sees_every_module_and_init_values(config):
    model = ScriptedModel([brief(), valid_draft()])

    design_patch("bass", model=model, config=config)

    prompt = model.prompts[1]
    assert "FX Distortion:" in prompt and "- Dist_Mode: one of: Tube, SoftClip" in prompt
    assert "- Filter On: one of: Off, On (Init: Off)" in prompt
    assert "Mod 1 amt" not in prompt  # the mod matrix arrives with ticket 05


def test_parameters_outside_the_design_scope_are_rejected(config):
    draft = valid_draft(values=[ParameterValue(name="Mod 1 amt", value=50.0)])
    model = ScriptedModel([brief(), draft])

    result = design_patch("bass", model=model, config=replace(config, max_retries=0))

    assert not result.validation.passed
    assert any("Mod 1 amt" in e for e in result.validation.errors)


def test_a_drafts_routings_end_up_in_the_preset(config):
    draft = valid_draft(
        routings=[
            RoutingDraft(source="LFO 1", destination="Fil Cutoff", amount=40.0),
            RoutingDraft(source="Env 2", destination="Fil Cutoff", amount=25.0, bipolar=False),
        ]
    )

    result = design_patch("wobble bass", model=ScriptedModel([brief(), draft]), config=config)

    routings = fxp.read(result.preset_path.read_bytes()).routings
    assert [(r.source, r.destination) for r in routings] == [
        ("LFO 1", "Fil Cutoff"),
        ("Env 2", "Fil Cutoff"),
    ]


@pytest.mark.parametrize(
    ("routing", "complaint"),
    [
        (RoutingDraft(source="LFO 7", destination="Fil Cutoff", amount=40.0), "LFO 7"),
        (RoutingDraft(source="LFO 1", destination="Fil Type", amount=40.0), "Fil Type"),
        (RoutingDraft(source="LFO 1", destination="Fil Cutoff", amount=140.0), "140"),
    ],
)
def test_bad_routings_are_sent_back_to_the_model(config, routing, complaint):
    model = ScriptedModel([brief(), valid_draft(routings=[routing]), valid_draft()])

    result = design_patch("wobble bass", model=model, config=config)

    assert result.validation.retries == 1
    assert complaint in model.prompts[-1]


def test_the_model_sees_the_modulation_sources_and_destinations(config):
    model = ScriptedModel([brief(), valid_draft()])

    design_patch("bass", model=model, config=config)

    prompt = model.prompts[1]
    assert "Modulation sources: Mod Wheel, Env 1, Env 2" in prompt
    assert "Fil Cutoff" in prompt.split("Modulation destinations:")[1]


def test_note_values_in_a_name_stay_readable(config):
    model = ScriptedModel([brief(name="Wobble 1/8 Bass"), valid_draft()])

    result = design_patch("wobble", model=model, config=config)

    assert result.preset_path.stem == "Wobble 1-8 Bass"


def test_more_routings_than_the_matrix_holds_are_rejected(config):
    routings = [RoutingDraft(source="LFO 1", destination="Fil Cutoff", amount=1.0)] * 33
    model = ScriptedModel([brief(), valid_draft(routings=routings)])

    result = design_patch("bass", model=model, config=replace(config, max_retries=0))

    assert any("33 routings" in e for e in result.validation.errors)
