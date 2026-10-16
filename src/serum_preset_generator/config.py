"""File-path configuration from the environment (and a `.env` file). No model

or provider setting lives here — there's no model in this codebase (ADR 0004).

DesignConfig (all optional):
    SERUM_GEN_OUTPUT_DIR     default Serum's Presets/User/AI folder
    SERUM_GEN_TEMPLATE       default the packaged Init preset
    SERUM_GEN_SERUM_ROOT     default /Library/Audio/Presets/Xfer Records/Serum Presets
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from .design import DesignConfig
from .resources import default_template

DEFAULT_SERUM_ROOT = Path("/Library/Audio/Presets/Xfer Records/Serum Presets")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_environment() -> None:
    """Load `.env` from the working directory, then from the project root.

    Variables already set in the environment win.
    """
    load_dotenv(Path.cwd() / ".env")
    load_dotenv(PROJECT_ROOT / ".env")


def _configured_serum_root() -> Path | None:
    """SERUM_GEN_SERUM_ROOT, or None if it isn't really set.

    An MCP host (e.g. Claude Desktop's .mcpb installer) that leaves the
    optional "Serum presets folder" field blank may pass its unresolved
    `${user_config.serum_root}` template through as the env var instead of
    omitting it or substituting an empty string. Treat that, and a blank
    value, the same as unset so the default location is used.
    """
    value = os.environ.get("SERUM_GEN_SERUM_ROOT", "").strip()
    if not value or value.startswith("${"):
        return None
    return Path(value)


def load_design_config() -> DesignConfig:
    serum_root = _configured_serum_root() or DEFAULT_SERUM_ROOT
    template_path = os.environ.get("SERUM_GEN_TEMPLATE")
    template = Path(template_path).read_bytes() if template_path else default_template()
    return DesignConfig(
        output_dir=Path(
            os.environ.get("SERUM_GEN_OUTPUT_DIR", serum_root / "Presets" / "User" / "AI")
        ),
        template=template,
        wavetables=factory_wavetables(serum_root / "Tables"),
    )


def library_dir() -> Path:
    """Serum's preset library, searched when a Preset is named rather than given by path."""
    return (_configured_serum_root() or DEFAULT_SERUM_ROOT) / "Presets"


def factory_wavetables(tables_dir: Path) -> frozenset[str] | None:
    """Wavetable paths relative to Serum's Tables folder, as presets store them."""
    if not tables_dir.is_dir():
        return None
    return frozenset(p.relative_to(tables_dir).as_posix() for p in tables_dir.rglob("*.wav"))


def resolve(config: DesignConfig | None) -> DesignConfig:
    """Fill in `config` from the environment (and `.env`) if the caller didn't inject one."""
    if config is None:
        load_environment()
    return config or load_design_config()
