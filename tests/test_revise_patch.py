"""Revisions at the pipeline seam: an existing Preset plus feedback → a new Preset."""

from dataclasses import replace

import pytest
from fake_model import ScriptedModel
from test_constraints import v
from test_design_patch import brief, valid_draft

from serum_preset_generator import fxp
from serum_preset_generator.patch import Patch, Routing
from serum_preset_generator.pipeline import RoutingDraft, revise_patch
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


def harder(**changes):
    return valid_draft(values=v(**changes), wavetable_a=None, recipe="Dist_Drv up: more bite.")


def test_a_revision_applies_only_the_proposed_changes(config, boom):
    original = boom.read_bytes()
    model = ScriptedModel([brief(), harder(Dist_Drv=55.0, Env1_Dec=0.5)])

    result = revise_patch(boom, "hit harder", model=model, config=config)

    assert result.preset_path == config.output_dir / "808 Boom_v2.fxp"
    before, after = fxp.read(original), fxp.read(result.preset_path.read_bytes())
    assert after.params["Dist_Drv"] == pytest.approx(55.0, rel=1e-4)
    assert after.params["Env1 Dec"] == pytest.approx(0.5, rel=1e-4)
    unchanged = {k: x for k, x in before.params.items() if k not in ("Dist_Drv", "Env1 Dec")}
    assert {k: after.params[k] for k in unchanged} == unchanged
    assert after.routings == before.routings  # routings: null keeps the matrix
    assert after.wavetable_a == before.wavetable_a  # null keeps the wavetable
    assert boom.read_bytes() == original  # the original is never touched
    assert result.recipe == "Dist_Drv up: more bite."
    assert "Dist_Drv: 20 % → 55 %" in result.changes


def test_the_model_sees_the_current_preset_and_the_feedback(config, boom):
    model = ScriptedModel([brief(), harder(Dist_Drv=55.0)])

    revise_patch(boom, "hit harder", model=model, config=config)

    prompt = model.prompts[1]
    assert "hit harder" in prompt
    assert "- Dist_Drv: 0 to 100 % (now: 20 %)" in prompt
    assert "Env 2 → Sub Osc Level 30 %" in prompt


def test_revisions_are_numbered_and_never_overwrite(config, boom):
    first = revise_patch(boom, "harder", model=ScriptedModel([brief(), harder()]), config=config)
    second = revise_patch(boom, "harder", model=ScriptedModel([brief(), harder()]), config=config)
    of_v2 = revise_patch(
        first.preset_path, "harder", model=ScriptedModel([brief(), harder()]), config=config
    )

    assert first.preset_path.stem == "808 Boom_v2"
    assert second.preset_path.stem == "808 Boom_v3"
    assert of_v2.preset_path.stem == "808 Boom_v4"  # not "808 Boom_v2_v2"


def test_constraints_apply_to_the_whole_revised_patch(config, boom):
    # The original already has Distortion FX on; "keep the sub clean" must switch it off.
    model = ScriptedModel(
        [brief(constraints=["clean_sub"]), harder(Dist_Drv=60.0), harder(Dist_Enable="Off")]
    )

    result = revise_patch(boom, "harder, keep the sub clean", model=model, config=config)

    assert result.validation.retries == 1
    assert result.validation.constraints == {"clean_sub": True}


def test_exhausted_retries_write_nothing(config, boom):
    bad = harder(Fil_Reso=500.0)
    model = ScriptedModel([brief(), bad, bad])

    result = revise_patch(boom, "harder", model=model, config=replace(config, max_retries=1))

    assert result.preset_path is None
    assert not config.output_dir.exists() or not any(config.output_dir.iterdir())


def test_an_older_builds_preset_keeps_its_routings_but_takes_knob_changes(
    config, factory_library, tmp_path
):
    factory = factory_library / "Bass/BA Talk Wobz [ADWR].fxp"
    rerouted = harder(Dist_Drv=50.0).model_copy(
        update={"routings": [RoutingDraft(source="LFO 2", destination="Fil Cutoff", amount=20)]}
    )
    model = ScriptedModel([brief(), rerouted, harder(Fil_Reso=40.0)])

    result = revise_patch(factory, "harder", model=model, config=config)

    assert result.validation.retries == 1
    assert "older Serum build" in model.prompts[-1]
    after = fxp.read(result.preset_path.read_bytes())
    assert after.params["Fil Reso"] == pytest.approx(40.0, abs=1e-3)
    assert after.routings == fxp.read(factory.read_bytes()).routings


def test_routing_changes_are_listed_readably(config, boom):
    stronger = harder().model_copy(
        update={
            "routings": [
                RoutingDraft(source="Env 2", destination="Sub Osc Level", amount=45.0),
                RoutingDraft(source="LFO 1", destination="Fil Cutoff", amount=20.0),
            ]
        }
    )

    result = revise_patch(boom, "harder", model=ScriptedModel([brief(), stronger]), config=config)

    assert "Routing 1: Env 2 → Sub Osc Level 30 % → 45 %" in result.changes
    assert "Routing 2: (empty) → LFO 1 → Fil Cutoff 20 %" in result.changes
    assert not any(c.startswith("Mod 1 amt") for c in result.changes)


def test_knobs_an_older_preset_cannot_hold_are_refused_not_lost(config, factory_library):
    # Older builds ignore the tail of the second parameter block (Comp_Wet lives there).
    factory = factory_library / "Misc/PR 808 Kick Circuit [SD].fxp"
    model = ScriptedModel([brief(), harder(Comp_Wet=50.0), harder(Dist_Drv=50.0)])

    result = revise_patch(factory, "harder", model=model, config=config)

    assert result.validation.retries == 1
    assert "Comp_Wet" in model.prompts[-1] and "older Serum build" in model.prompts[-1]
    assert "Comp_Wet" not in model.prompts[1].split("The preset now")[1].split("Current")[0]
    assert result.changes == ["Dist_Drv: 25 % → 50 %"]


def test_a_failed_write_leaves_no_file(config, boom, monkeypatch):
    def broken_write(patch, base):
        raise fxp.FxpError("disk says no")

    monkeypatch.setattr(fxp, "write", broken_write)

    with pytest.raises(fxp.FxpError):
        revise_patch(boom, "harder", model=ScriptedModel([brief(), harder()]), config=config)

    assert not config.output_dir.exists() or not any(config.output_dir.iterdir())


def test_long_names_stay_within_serums_limit(config, tmp_path):
    long = tmp_path / "An Extremely Long Preset Name Xyz.fxp"  # 33 characters
    long.write_bytes(fxp.write(BOOM, base=default_template()))

    result = revise_patch(long, "harder", model=ScriptedModel([brief(), harder()]), config=config)

    assert result.preset_path.stem.endswith("_v2")
    assert len(result.preset_path.stem) <= 31
