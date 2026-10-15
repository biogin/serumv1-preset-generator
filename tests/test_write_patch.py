"""`write_patch` at the design seam: a Patch the caller already built → a Preset."""

import pytest

from serum_preset_generator import fxp
from serum_preset_generator.design import write_patch
from serum_preset_generator.patch import Patch, Routing


def patch(name="Cyber Bass", **overrides):
    fields = {
        "params": {"Fil Type": "German LP", "Fil Cutoff": 180.0, "Fil Reso": 35.0},
        "wavetable_a": "Analog/PWM Juno.wav",
    }
    return Patch(name=name, **{**fields, **overrides})


def test_a_valid_patch_is_written_with_a_summary(config):
    result = write_patch(patch(), config=config)

    assert result.preset_path == config.output_dir / "Cyber Bass.fxp"
    written = fxp.read(result.preset_path.read_bytes())
    assert written.name == "Cyber Bass"
    assert written.params["Fil Type"] == "German LP"
    assert written.params["Fil Cutoff"] == pytest.approx(180.0, rel=1e-4)
    assert written.params["Fil Reso"] == pytest.approx(35.0, abs=1e-4)
    assert written.wavetable_a == "Analog/PWM Juno.wav"
    assert "Fil Type: German LP" in result.summary
    assert "Osc A wavetable: Analog/PWM Juno.wav" in result.summary
    assert result.validation.passed


def test_an_invalid_patch_is_rejected_and_nothing_is_written(config):
    result = write_patch(patch(params={"Fil Cutoff": 99999.0}), config=config)

    assert not result.validation.passed
    assert any("Fil Cutoff" in e and "99999" in e for e in result.validation.errors)
    assert result.preset_path is None
    assert not config.output_dir.exists() or not any(config.output_dir.iterdir())


def test_an_unknown_wavetable_is_rejected(config):
    result = write_patch(patch(wavetable_a="Made Up/Table.wav"), config=config)

    assert not result.validation.passed
    assert any("Made Up/Table.wav" in e for e in result.validation.errors)
    assert result.preset_path is None


def test_an_existing_preset_is_never_overwritten(config):
    first = write_patch(patch(), config=config)
    second = write_patch(patch(), config=config)

    assert first.preset_path == config.output_dir / "Cyber Bass.fxp"
    assert second.preset_path == config.output_dir / "Cyber Bass_2.fxp"
    assert fxp.read(second.preset_path.read_bytes()).name == "Cyber Bass_2"


def test_a_preset_name_serum_cannot_store_is_made_safe(config):
    result = write_patch(patch(name="Кибер/Бас: очень злой и перегруженный"), config=config)

    name = result.preset_path.stem
    assert name.isascii() and "/" not in name and len(name) <= 31
    assert fxp.read(result.preset_path.read_bytes()).name == name


def test_numbered_names_still_fit_serums_31_characters(config):
    stem = "A Very Long Preset Name Here"  # 28 characters
    config.output_dir.mkdir(parents=True)
    for n in ["", *(f"_{i}" for i in range(2, 101))]:
        (config.output_dir / f"{stem}{n}.fxp").write_bytes(b"")

    result = write_patch(patch(name=stem), config=config)

    assert len(result.preset_path.stem) <= 31
    assert fxp.read(result.preset_path.read_bytes()).name == result.preset_path.stem


def test_a_patch_can_use_any_module_in_the_reference(config):
    result = write_patch(
        patch(
            params={
                "A Unison": 7,
                "A UniDet": 0.3,
                "Filter On": "On",
                "Dist Enable": "On",
                "Dist_Mode": "Diode 1",
                "Dist_Drv": 60.0,
                "Env1 Rel": 0.4,
                "Dly_TimL": "1/8",
            },
            wavetable_a=None,
        ),
        config=config,
    )

    written = fxp.read(result.preset_path.read_bytes()).params
    assert written["A Unison"] == 7
    assert written["A UniDet"] == pytest.approx(0.3, rel=1e-3)
    assert (written["Filter On"], written["Dist Enable"]) == ("On", "On")
    assert written["Dist_Mode"] == "Diode 1"
    assert written["Env1 Rel"] == pytest.approx(0.4, rel=1e-3)
    assert written["Dly_TimL"] == "1/8"


def test_a_parameter_outside_the_design_scope_is_rejected(config):
    result = write_patch(patch(params={"Mod 1 amt": 50.0}), config=config)

    assert not result.validation.passed
    assert any("Mod 1 amt" in e for e in result.validation.errors)


def test_routings_end_up_in_the_preset(config):
    result = write_patch(
        patch(
            routings=[
                Routing("LFO 1", "Fil Cutoff", 40.0),
                Routing("Env 2", "Fil Cutoff", 25.0, bipolar=False),
            ]
        ),
        config=config,
    )

    routings = fxp.read(result.preset_path.read_bytes()).routings
    assert [(r.source, r.destination) for r in routings] == [
        ("LFO 1", "Fil Cutoff"),
        ("Env 2", "Fil Cutoff"),
    ]


@pytest.mark.parametrize(
    ("routing", "complaint"),
    [
        (Routing("LFO 7", "Fil Cutoff", 40.0), "LFO 7"),
        (Routing("LFO 1", "Fil Type", 40.0), "Fil Type"),
        (Routing("LFO 1", "Fil Cutoff", 140.0), "140"),
    ],
)
def test_bad_routings_are_rejected(config, routing, complaint):
    result = write_patch(patch(routings=[routing]), config=config)

    assert not result.validation.passed
    assert any(complaint in e for e in result.validation.errors)


def test_note_values_in_a_name_stay_readable(config):
    result = write_patch(patch(name="Wobble 1/8 Bass"), config=config)

    assert result.preset_path.stem == "Wobble 1-8 Bass"


def test_more_routings_than_the_matrix_holds_are_rejected(config):
    result = write_patch(patch(routings=[Routing("LFO 1", "Fil Cutoff", 1.0)] * 33), config=config)

    assert any("33 routings" in e for e in result.validation.errors)
