from serum_preset_generator import config


def test_output_dir_defaults_to_serums_ai_folder(monkeypatch):
    monkeypatch.delenv("SERUM_GEN_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("SERUM_GEN_SERUM_ROOT", raising=False)

    loaded = config.load_design_config()

    assert loaded.output_dir == config.DEFAULT_SERUM_ROOT / "Presets" / "User" / "AI"


def test_output_dir_is_configurable(monkeypatch, tmp_path):
    monkeypatch.setenv("SERUM_GEN_OUTPUT_DIR", str(tmp_path))

    assert config.load_design_config().output_dir == tmp_path


def test_blank_serum_root_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("SERUM_GEN_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("SERUM_GEN_SERUM_ROOT", "")

    loaded = config.load_design_config()

    assert loaded.output_dir == config.DEFAULT_SERUM_ROOT / "Presets" / "User" / "AI"


def test_unresolved_user_config_template_falls_back_to_default(monkeypatch):
    """An MCP host that leaves the optional config field blank may pass its

    unresolved `${user_config.serum_root}` placeholder through as-is instead
    of a real path or an empty string.
    """
    monkeypatch.delenv("SERUM_GEN_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("SERUM_GEN_SERUM_ROOT", "${user_config.serum_root}")

    loaded = config.load_design_config()

    assert loaded.output_dir == config.DEFAULT_SERUM_ROOT / "Presets" / "User" / "AI"


def test_a_real_configured_serum_root_is_honoured(monkeypatch, tmp_path):
    """The happy path: a producer actually picked a non-standard install folder."""
    monkeypatch.delenv("SERUM_GEN_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("SERUM_GEN_SERUM_ROOT", str(tmp_path))
    (tmp_path / "Tables").mkdir()
    (tmp_path / "Tables" / "Reese.wav").touch()

    loaded = config.load_design_config()

    assert loaded.output_dir == tmp_path / "Presets" / "User" / "AI"
    assert loaded.wavetables == frozenset({"Reese.wav"})


def test_factory_wavetables_is_none_when_the_tables_folder_is_missing(tmp_path):
    assert config.factory_wavetables(tmp_path / "Tables") is None


def test_library_dir_defaults_to_the_standard_location(monkeypatch):
    monkeypatch.delenv("SERUM_GEN_SERUM_ROOT", raising=False)

    assert config.library_dir() == config.DEFAULT_SERUM_ROOT / "Presets"


def test_library_dir_respects_a_custom_serum_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SERUM_GEN_SERUM_ROOT", str(tmp_path))

    assert config.library_dir() == tmp_path / "Presets"


def test_library_dir_falls_back_on_a_blank_serum_root(monkeypatch):
    monkeypatch.setenv("SERUM_GEN_SERUM_ROOT", "")

    assert config.library_dir() == config.DEFAULT_SERUM_ROOT / "Presets"


def test_library_dir_falls_back_on_an_unresolved_user_config_template(monkeypatch):
    monkeypatch.setenv("SERUM_GEN_SERUM_ROOT", "${user_config.serum_root}")

    assert config.library_dir() == config.DEFAULT_SERUM_ROOT / "Presets"


def test_resolve_keeps_an_injected_config(tmp_path):
    injected = config.load_design_config()

    assert config.resolve(injected) is injected


def test_resolve_with_no_injected_config_loads_from_the_environment(monkeypatch):
    """This is the exact path every MCP tool call takes (`config = resolve(config)`

    with no config pre-injected) — the one that silently used an unresolved
    `${user_config.serum_root}` env value in production before that was fixed.
    """
    monkeypatch.delenv("SERUM_GEN_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("SERUM_GEN_SERUM_ROOT", raising=False)

    loaded = config.resolve(None)

    assert loaded.output_dir == config.DEFAULT_SERUM_ROOT / "Presets" / "User" / "AI"
