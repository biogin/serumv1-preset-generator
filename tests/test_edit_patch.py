"""`edit_patch` at the design seam: an existing Preset plus a partial Patch → a Revision."""

import pytest
from test_constraints import v

from serum_preset_generator import fxp
from serum_preset_generator.design import edit_patch
from serum_preset_generator.patch import Patch, Routing
from serum_preset_generator.resources import default_template

BOOM = Patch(
    "808 Boom",
    {"Osc S On": "On", "Sub Osc Level": 80.0, "Dist Enable": "On", "Dist_Drv": 20.0,
     "Env1 Dec": 0.8},
    routings=[Routing("Env 2", "Sub Osc Level", 30.0)],
)  # fmt: skip


@pytest.fixture
def boom(tmp_path):
    path = tmp_path / "library" / "808 Boom.fxp"
    path.parent.mkdir()
    path.write_bytes(fxp.write(BOOM, base=default_template()))
    return path


def changes(**settings):
    return Patch(name="", params=v(**settings))


def test_a_revision_applies_only_the_proposed_changes(config, boom):
    original = boom.read_bytes()

    result = edit_patch(boom, changes(Dist_Drv=55.0, Env1_Dec=0.5), config=config)

    assert result.preset_path == config.output_dir / "808 Boom_v2.fxp"
    before, after = fxp.read(original), fxp.read(result.preset_path.read_bytes())
    assert after.params["Dist_Drv"] == pytest.approx(55.0, rel=1e-4)
    assert after.params["Env1 Dec"] == pytest.approx(0.5, rel=1e-4)
    unchanged = {k: x for k, x in before.params.items() if k not in ("Dist_Drv", "Env1 Dec")}
    assert {k: after.params[k] for k in unchanged} == unchanged
    assert after.routings == before.routings  # routings: None keeps the matrix
    assert after.wavetable_a == before.wavetable_a  # None keeps the wavetable
    assert boom.read_bytes() == original  # the original is never touched
    assert "Dist_Drv: 55 %" in result.summary
    assert "Dist_Drv: 20 % → 55 %" in result.changes


def test_revisions_are_numbered_and_never_overwrite(config, boom):
    first = edit_patch(boom, changes(Dist_Drv=55.0), config=config)
    second = edit_patch(boom, changes(Dist_Drv=55.0), config=config)
    of_v2 = edit_patch(first.preset_path, changes(Dist_Drv=55.0), config=config)

    assert first.preset_path.stem == "808 Boom_v2"
    assert second.preset_path.stem == "808 Boom_v3"
    assert of_v2.preset_path.stem == "808 Boom_v4"  # not "808 Boom_v2_v2"


def test_constraints_apply_to_the_whole_revised_patch(config, boom):
    # The original already has Distortion FX on; "keep the sub clean" must switch it off.
    broken = edit_patch(boom, changes(Dist_Drv=60.0), constraints=["clean_sub"], config=config)
    held = edit_patch(boom, changes(Dist_Enable="Off"), constraints=["clean_sub"], config=config)

    assert broken.validation.constraints == {"clean_sub": False}
    assert held.validation.constraints == {"clean_sub": True}


def test_an_invalid_change_writes_nothing(config, boom):
    result = edit_patch(boom, changes(Fil_Reso=500.0), config=config)

    assert result.preset_path is None
    assert not result.validation.passed
    assert not config.output_dir.exists() or not any(config.output_dir.iterdir())


def test_an_older_builds_preset_keeps_its_routings_but_takes_knob_changes(config, factory_library):
    factory = factory_library / "Bass/BA Talk Wobz [ADWR].fxp"
    rerouted = Patch(
        name="", params=v(Dist_Drv=50.0), routings=[Routing("LFO 2", "Fil Cutoff", 20.0)]
    )

    rejected = edit_patch(factory, rerouted, config=config)
    result = edit_patch(factory, changes(Fil_Reso=40.0), config=config)

    assert "older Serum build" in "\n".join(rejected.validation.errors)
    after = fxp.read(result.preset_path.read_bytes())
    assert after.params["Fil Reso"] == pytest.approx(40.0, abs=1e-3)
    assert after.routings == fxp.read(factory.read_bytes()).routings


def test_routing_changes_are_listed_readably(config, boom):
    stronger = Patch(
        name="",
        params=v(),
        routings=[
            Routing("Env 2", "Sub Osc Level", 45.0),
            Routing("LFO 1", "Fil Cutoff", 20.0),
        ],
    )

    result = edit_patch(boom, stronger, config=config)

    assert "Routing 1: Env 2 → Sub Osc Level 30 % → 45 %" in result.changes
    assert "Routing 2: (empty) → LFO 1 → Fil Cutoff 20 %" in result.changes
    assert not any(c.startswith("Mod 1 amt") for c in result.changes)


def test_knobs_an_older_preset_cannot_hold_are_refused_not_lost(config, factory_library):
    # Older builds ignore the tail of the second parameter block (Comp_Wet lives there).
    factory = factory_library / "Misc/PR 808 Kick Circuit [SD].fxp"

    rejected = edit_patch(factory, changes(Comp_Wet=50.0), config=config)
    result = edit_patch(factory, changes(Dist_Drv=50.0), config=config)

    errors = "\n".join(rejected.validation.errors)
    assert "Comp_Wet" in errors and "older Serum build" in errors
    assert result.changes == ["Dist_Drv: 25 % → 50 %"]


def test_a_failed_write_leaves_no_file(config, boom, monkeypatch):
    def broken_write(patch, base):
        raise fxp.FxpError("disk says no")

    monkeypatch.setattr(fxp, "write", broken_write)

    with pytest.raises(fxp.FxpError):
        edit_patch(boom, changes(Dist_Drv=55.0), config=config)

    assert not config.output_dir.exists() or not any(config.output_dir.iterdir())


def test_long_names_stay_within_serums_limit(config, tmp_path):
    long = tmp_path / "An Extremely Long Preset Name Xyz.fxp"  # 33 characters
    long.write_bytes(fxp.write(BOOM, base=default_template()))

    result = edit_patch(long, changes(Dist_Drv=55.0), config=config)

    assert result.preset_path.stem.endswith("_v2")
    assert len(result.preset_path.stem) <= 31
