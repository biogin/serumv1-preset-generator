from importlib.resources import files

import pytest

from serum_preset_generator import fxp
from serum_preset_generator.patch import Patch


def init_template() -> bytes:
    return files("serum_preset_generator").joinpath("templates/init.fxp").read_bytes()


def test_rewriting_every_factory_preset_reproduces_its_bytes(factory_library):
    mismatches = []
    for path in sorted(factory_library.rglob("*.fxp")):
        original = path.read_bytes()
        if fxp.write(fxp.read(original), base=original) != original:
            mismatches.append(str(path.relative_to(factory_library)))

    assert mismatches == []


def test_an_empty_patch_on_the_init_template_reproduces_it():
    template = init_template()
    empty = Patch(name=fxp.read(template).name)

    assert fxp.write(empty, base=template) == template


def test_editing_one_parameter_changes_only_that_parameter():
    template = init_template()
    before = fxp.read(template)

    after = fxp.read(fxp.write(Patch(before.name, {"Fil Cutoff": 1000.0}), base=template))

    assert after.params["Fil Cutoff"] == pytest.approx(1000.0, rel=1e-4)
    assert {k: v for k, v in after.params.items() if k != "Fil Cutoff"} == {
        k: v for k, v in before.params.items() if k != "Fil Cutoff"
    }
    assert (after.name, after.wavetable_a, after.wavetable_b) == (
        before.name,
        before.wavetable_a,
        before.wavetable_b,
    )


def test_writes_filter_type_wavetables_and_preset_name():
    patch = Patch(
        "AI Cyber Bass",
        {"Fil Type": "German LP", "Fil Reso": 35.0},
        wavetable_a="Analog/PWM Juno.wav",
        wavetable_b="Digital/Kream.wav",
    )

    after = fxp.read(fxp.write(patch, base=init_template()))

    assert after.name == "AI Cyber Bass"
    assert after.params["Fil Type"] == "German LP"
    assert after.params["Fil Reso"] == pytest.approx(35.0, abs=1e-4)
    assert (after.wavetable_a, after.wavetable_b) == ("Analog/PWM Juno.wav", "Digital/Kream.wav")


@pytest.mark.parametrize(
    "params",
    [
        {"Fil Cutoff": 30000.0},
        {"Fil Reso": -1.0},
        {"Fil Type": "Moog Ladder"},
        {"Fil Cutof": 500.0},
    ],
)
def test_rejects_values_serum_cannot_hold(params):
    with pytest.raises(fxp.FxpError):
        fxp.write(Patch("x", params), base=init_template())


def test_rejects_a_preset_name_too_long_for_serum():
    with pytest.raises(fxp.FxpError):
        fxp.write(Patch("x" * 40), base=init_template())
