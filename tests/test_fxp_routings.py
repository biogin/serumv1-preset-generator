"""Modulation-matrix routings, through the FXP codec."""

import pytest

from serum_preset_generator import fxp
from serum_preset_generator.patch import Patch, Routing
from serum_preset_generator.resources import default_template


@pytest.mark.parametrize(
    ("preset", "expected"),
    [
        # Mined from the factory library; source/destination ids per FORMATS.md.
        ("Bass/BA Talk Wobz [ADWR].fxp", Routing("LFO 1", "Fil Cutoff", 48.897)),
        ("Bass/BA Ampology [CFA].fxp", Routing("Env 2", "Fil Cutoff", 51.754)),
        ("Bass/BA BSOD Sqr Bass [SD].fxp", Routing("Env 2", "Fil Cutoff", 100.0, bipolar=True)),
    ],
)
def test_reads_a_presets_routings(read_factory, preset, expected):
    first = read_factory(preset).routings[0]

    assert (first.source, first.destination, first.bipolar) == (
        expected.source,
        expected.destination,
        expected.bipolar,
    )
    assert first.amount == pytest.approx(expected.amount, abs=1e-3)


WOBBLE = [
    Routing("LFO 1", "Fil Cutoff", 45.0),
    Routing("Env 2", "Fil Cutoff", 30.0),
    Routing("Macro 1", "Dist_Drv", -20.0, bipolar=True),
]


def test_written_routings_read_back_in_slot_order():
    written = fxp.read(fxp.write(Patch("t", routings=WOBBLE), base=default_template()))

    assert [(r.source, r.destination, r.bipolar) for r in written.routings] == [
        ("LFO 1", "Fil Cutoff", False),
        ("Env 2", "Fil Cutoff", False),
        ("Macro 1", "Dist_Drv", True),
    ]
    assert [r.amount for r in written.routings] == pytest.approx([45.0, 30.0, -20.0])
    # Serum also shows each slot's amount as a parameter.
    assert written.params["Mod 1 amt"] == pytest.approx(45.0, abs=1e-3)
    assert written.params["Mod 3 amt"] == pytest.approx(-20.0, abs=1e-3)


def test_an_empty_list_clears_the_matrix_and_none_keeps_it():
    base = fxp.write(Patch("t", routings=WOBBLE), base=default_template())

    cleared = fxp.read(fxp.write(Patch("t", routings=[]), base=base))
    kept = fxp.read(fxp.write(Patch("t", routings=None), base=base))

    assert cleared.routings == []
    assert cleared.params["Mod 1 amt"] == 0
    assert kept.routings == fxp.read(base).routings


def test_all_32_slots_can_be_used():
    routings = [Routing("LFO 2", "A WTPos", float(i)) for i in range(32)]

    written = fxp.read(fxp.write(Patch("t", routings=routings), base=default_template()))

    assert [r.amount for r in written.routings] == pytest.approx([float(i) for i in range(32)])
    assert written.params["Mod32 amt"] == pytest.approx(31.0, abs=1e-3)


@pytest.mark.parametrize(
    "routing",
    [
        Routing("LFO 9", "Fil Cutoff", 50.0),
        Routing("LFO 1", "Fil Type", 50.0),  # not a destination in Serum's menu
        Routing("LFO 1", "Fil Cutoff", 150.0),
    ],
)
def test_rejects_routings_serum_cannot_hold(routing):
    with pytest.raises(fxp.FxpError):
        fxp.write(Patch("t", routings=[routing]), base=default_template())


def test_rejects_more_routings_than_slots():
    too_many = [Routing("LFO 1", "Fil Cutoff", 1.0)] * 33
    with pytest.raises(fxp.FxpError):
        fxp.write(Patch("t", routings=too_many), base=default_template())


def test_routings_keep_their_slot_numbers_across_empty_slots(read_factory):
    # Slot 7 is empty in this factory preset.
    routings = read_factory("Bass/BA SomeGrit [EE].fxp").routings

    assert [r.slot for r in routings] == [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13]


def test_routings_cannot_be_written_onto_an_older_builds_preset(factory_library):
    # Older builds number modulation sources differently.
    base = (factory_library / "Bass/BA Talk Wobz [ADWR].fxp").read_bytes()

    with pytest.raises(fxp.FxpError, match="older Serum build"):
        fxp.write(Patch("t", routings=WOBBLE), base=base)
