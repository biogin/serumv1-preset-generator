from serum_preset_generator import cli


def test_inspect_prints_preset_parameters_in_human_units(factory_library, capsys):
    exit_code = cli.main(["inspect", str(factory_library / "Bass/BA Ampology [CFA].fxp")])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "BA Ampology [CFA]" in out
    assert "Fil Type: German LP" in out
    assert "Fil Cutoff: 75.09 Hz" in out
    assert "MasterVol: 70 %" in out
    assert "Osc A wavetable: Digital/Kream.wav" in out
    assert "Osc B wavetable: (default)" in out
    # the full Parameter Reference, grouped by module
    assert "\nFX Distortion\n" in out
    assert "  Dist_Mode: " in out
    assert "  LFO8 Delay: 0 s" in out
    assert "  Filter On: " in out


def test_inspect_reports_unreadable_file_without_traceback(tmp_path, capsys):
    bogus = tmp_path / "not-a-preset.fxp"
    bogus.write_bytes(b"hello")

    exit_code = cli.main(["inspect", str(bogus)])

    assert exit_code == 1
    assert "not a Serum 1" in capsys.readouterr().err


def test_inspect_lists_the_mod_matrix(factory_library, capsys):
    cli.main(["inspect", str(factory_library / "Bass/BA Talk Wobz [ADWR].fxp")])

    out = capsys.readouterr().out
    assert "\nModulation matrix\n" in out
    assert "  1: LFO 1 → Fil Cutoff 48.9 %" in out


def test_a_missing_or_unknown_command_is_a_usage_error(capsys):
    exit_code = cli.main([])

    assert exit_code == 1
    assert "usage: serum-gen inspect" in capsys.readouterr().err
