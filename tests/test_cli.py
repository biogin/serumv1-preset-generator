from serum_preset_generator import cli


def test_inspect_prints_preset_parameters_in_human_units(factory_library, capsys):
    exit_code = cli.main(["inspect", str(factory_library / "Bass/BA Ampology [CFA].fxp")])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "BA Ampology [CFA]" in out
    assert "Fil Type: German LP" in out
    assert "Fil Cutoff: 75.1 Hz" in out
    assert "MasterVol: 70.0 %" in out
    assert "Osc A wavetable: Digital/Kream.wav" in out
    assert "Osc B wavetable: (default)" in out


def test_inspect_reports_unreadable_file_without_traceback(tmp_path, capsys):
    bogus = tmp_path / "not-a-preset.fxp"
    bogus.write_bytes(b"hello")

    exit_code = cli.main(["inspect", str(bogus)])

    assert exit_code == 1
    assert "not a Serum 1" in capsys.readouterr().err


def test_design_prints_the_recipe_and_where_the_preset_went(tmp_path, capsys):
    from fake_model import ScriptedModel
    from test_design_patch import brief, valid_draft

    from serum_preset_generator.pipeline import DesignConfig

    config = DesignConfig(output_dir=tmp_path, template=_init_template())
    model = ScriptedModel([brief(), valid_draft()])

    exit_code = cli.main(["aggressive", "cyberpunk", "bass"], model=model, config=config)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert valid_draft().recipe in out
    assert str(tmp_path / "Cyber Bass.fxp") in out


def test_design_reports_failure_without_writing(tmp_path, capsys):
    from fake_model import ScriptedModel
    from test_design_patch import brief, valid_draft

    from serum_preset_generator.pipeline import DesignConfig, Draft, ParameterValue

    bad: Draft = valid_draft(values=[ParameterValue(name="Nope", value=1.0)])
    config = DesignConfig(output_dir=tmp_path, template=_init_template(), max_retries=0)

    exit_code = cli.main(["bass"], model=ScriptedModel([brief(), bad]), config=config)

    assert exit_code == 1
    assert "Nope" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def _init_template() -> bytes:
    from serum_preset_generator.config import default_template

    return default_template()


def test_a_description_starting_with_inspect_is_still_a_description(tmp_path, capsys):
    from fake_model import ScriptedModel
    from test_design_patch import brief, valid_draft

    from serum_preset_generator.pipeline import DesignConfig

    config = DesignConfig(output_dir=tmp_path, template=_init_template())

    exit_code = cli.main(
        ["inspect", "this", "pad"], model=ScriptedModel([brief(), valid_draft()]), config=config
    )

    assert exit_code == 0
    assert "Preset:" in capsys.readouterr().out
