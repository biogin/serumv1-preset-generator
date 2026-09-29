"""Configuration from the environment (and a `.env` file), plus the model factory.

DesignConfig (all optional):
    ANTHROPIC_API_KEY        read by the Anthropic SDK itself
    SERUM_GEN_PROVIDER       default anthropic (ollama arrives with ticket 07)
    SERUM_GEN_MODEL          default claude-sonnet-5-5
    SERUM_GEN_EFFORT         default medium
    SERUM_GEN_OUTPUT_DIR     default Serum's Presets/User/AI folder
    SERUM_GEN_TEMPLATE       default the packaged Init preset
    SERUM_GEN_SERUM_ROOT     default /Library/Audio/Presets/Xfer Records/Serum Presets
    SERUM_GEN_MAX_RETRIES    default 3
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from .pipeline import DesignConfig
from .resources import default_template

DEFAULT_SERUM_ROOT = Path("/Library/Audio/Presets/Xfer Records/Serum Presets")
DEFAULT_MODEL = "claude-sonnet-5-5"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(ValueError):
    """The environment asks for something this build can't do."""


def load_environment() -> None:
    """Load `.env` from the working directory, then from the project root.

    Variables already set in the environment win.
    """
    load_dotenv(Path.cwd() / ".env")
    load_dotenv(PROJECT_ROOT / ".env")


def load_design_config() -> DesignConfig:
    serum_root = Path(os.environ.get("SERUM_GEN_SERUM_ROOT", DEFAULT_SERUM_ROOT))
    template_path = os.environ.get("SERUM_GEN_TEMPLATE")
    template = Path(template_path).read_bytes() if template_path else default_template()
    return DesignConfig(
        output_dir=Path(
            os.environ.get("SERUM_GEN_OUTPUT_DIR", serum_root / "Presets" / "User" / "AI")
        ),
        template=template,
        max_retries=int(os.environ.get("SERUM_GEN_MAX_RETRIES", str(DesignConfig.max_retries))),
        wavetables=factory_wavetables(serum_root / "Tables"),
    )


def factory_wavetables(tables_dir: Path) -> frozenset[str] | None:
    """Wavetable paths relative to Serum's Tables folder, as presets store them."""
    if not tables_dir.is_dir():
        return None
    return frozenset(p.relative_to(tables_dir).as_posix() for p in tables_dir.rglob("*.wav"))


def make_model() -> BaseChatModel:
    provider = os.environ.get("SERUM_GEN_PROVIDER", "anthropic")
    if provider != "anthropic":
        raise ConfigError(
            f"SERUM_GEN_PROVIDER={provider!r} isn't available; use 'anthropic' "
            "(a local 'ollama' option is planned in ticket 07)"
        )
    return ChatAnthropic(
        model_name=os.environ.get("SERUM_GEN_MODEL", DEFAULT_MODEL),
        max_tokens_to_sample=16000,
        timeout=None,
        stop=None,
        output_config={"effort": os.environ.get("SERUM_GEN_EFFORT", "medium")},
        # On a safety-classifier refusal, the API re-runs the request on a
        # fallback model it picks by refusal category, inside the same call.
        betas=["server-side-fallback-2026-07-01"],
        model_kwargs={"fallbacks": "default"},
    )
