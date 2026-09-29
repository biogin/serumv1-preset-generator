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
