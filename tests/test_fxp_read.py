import pytest

from serum_preset_generator import fxp
from serum_preset_generator.parameter_reference import FILTER_TYPES


def test_reads_preset_name_and_master_volume(read_factory):
    patch = read_factory("Bass/BA Ampology [CFA].fxp")

    assert patch.name == "BA Ampology [CFA]"
    assert patch.params["MasterVol"] == pytest.approx(70.0, abs=0.01)


def test_preset_name_has_no_stray_spaces(read_factory):
    assert read_factory("Leads/LD Heavy Metal[SD].fxp").name == "LD Heavy Metal"


@pytest.mark.parametrize(
    ("preset", "filter_type"),
    [
        ("Bass/BA Ampology [CFA].fxp", "German LP"),
        ("Leads/LD Analogesque [EE].fxp", "MG Low 12"),
        # Saved by an older build (88 filter types): 87/88 exactly, while the
        # current build's divisor gives 93.9, a near-miss that must not round.
        ("Leads/LD LimoDriver [GS].fxp", "Formant-II"),
    ],
)
def test_decodes_filter_type_by_name(read_factory, preset, filter_type):
    assert read_factory(preset).params["Fil Type"] == filter_type


@pytest.mark.parametrize(
    ("preset", "hz"),
    [
        # Values Serum itself displays for these knob positions.
        ("Bass/BA Ampology [CFA].fxp", 75.0),
        ("Pads/PD Beating Pad [AS].fxp", 198.0),
    ],
)
def test_reads_filter_cutoff_in_hz(read_factory, preset, hz):
    assert read_factory(preset).params["Fil Cutoff"] == pytest.approx(hz, rel=0.01)


def test_reads_levels_and_resonance_in_percent(read_factory):
    ampology = read_factory("Bass/BA Ampology [CFA].fxp")
    pluck = read_factory("Bass/BA Analog Pluck [SN].fxp")

    assert ampology.params["A Vol"] == pytest.approx(40.35, abs=0.01)
    assert pluck.params["Fil Reso"] == pytest.approx(18.84, abs=0.01)


def test_reads_oscillator_wavetable_names(read_factory):
    patch = read_factory("Leads/LD Analogesque [EE].fxp")

    assert patch.wavetable_a == "Vowel/Native Curse.wav"
    assert patch.wavetable_b == "Analog/PWM Juno.wav"


def test_oscillator_on_serums_builtin_table_has_no_wavetable_name(read_factory):
    assert read_factory("Bass/BA Ampology [CFA].fxp").wavetable_b is None


def test_every_factory_preset_reads(factory_library):
    presets = sorted(factory_library.rglob("*.fxp"))
    assert presets

    failures = {}
    for path in presets:
        try:
            patch = fxp.read(path.read_bytes())
            assert patch.params["Fil Type"] in FILTER_TYPES
        except Exception as e:  # collect all failures, not just the first
            failures[str(path.relative_to(factory_library))] = repr(e)

    assert failures == {}


def test_rejects_bytes_that_are_not_a_serum_preset():
    with pytest.raises(fxp.FxpError):
        fxp.read(b"RIFF\x00\x00\x00\x00WAVEfmt ")


def test_rejects_a_truncated_preset(factory_library):
    data = (factory_library / "Bass/BA Ampology [CFA].fxp").read_bytes()

    with pytest.raises(fxp.FxpError):
        fxp.read(data[:200])


def test_rejects_a_preset_whose_trailer_does_not_match_its_state(factory_library):
    data = bytearray((factory_library / "Bass/BA Ampology [CFA].fxp").read_bytes())
    data[-4:] = (0).to_bytes(4, "little")

    with pytest.raises(fxp.FxpError):
        fxp.read(bytes(data))
