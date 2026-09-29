import pytest

from serum_preset_generator import config


def test_the_provider_defaults_to_anthropic_on_sonnet(monkeypatch):
    monkeypatch.delenv("SERUM_GEN_PROVIDER", raising=False)
    monkeypatch.delenv("SERUM_GEN_MODEL", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    assert config.make_model().model == "claude-sonnet-5-5"


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_an_unavailable_provider_is_a_clear_error(monkeypatch, provider):
    monkeypatch.setenv("SERUM_GEN_PROVIDER", provider)

    with pytest.raises(config.ConfigError, match=provider):
        config.make_model()
