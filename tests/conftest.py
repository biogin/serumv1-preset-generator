from collections.abc import Callable
from pathlib import Path

import pytest

from serum_preset_generator import fxp
from serum_preset_generator.patch import Patch

FACTORY_LIBRARY = Path("/Library/Audio/Presets/Xfer Records/Serum Presets/Presets")


@pytest.fixture
def factory_library() -> Path:
    """Serum 1's installed factory presets; tests using it skip when Serum isn't installed."""
    if not FACTORY_LIBRARY.is_dir():
        pytest.skip("Serum 1 factory library not installed")
    return FACTORY_LIBRARY


@pytest.fixture
def read_factory(factory_library: Path) -> Callable[[str], Patch]:
    def read(relative: str) -> Patch:
        return fxp.read((factory_library / relative).read_bytes())

    return read
