from serum_preset_generator import config


def test_output_dir_defaults_to_serums_ai_folder(monkeypatch):
    monkeypatch.delenv("SERUM_GEN_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("SERUM_GEN_SERUM_ROOT", raising=False)

    loaded = config.load_design_config()

    assert loaded.output_dir == config.DEFAULT_SERUM_ROOT / "Presets" / "User" / "AI"


def test_output_dir_is_configurable(monkeypatch, tmp_path):
    monkeypatch.setenv("SERUM_GEN_OUTPUT_DIR", str(tmp_path))

    assert config.load_design_config().output_dir == tmp_path


def test_resolve_keeps_an_injected_config(tmp_path):
    injected = config.load_design_config()

    assert config.resolve(injected) is injected
