import pytest
from fake_model import ScriptedModel

from serum_preset_generator import fxp
from serum_preset_generator.config import default_template
from serum_preset_generator.pipeline import Brief, DesignConfig, Draft, ParameterValue, design_patch


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
