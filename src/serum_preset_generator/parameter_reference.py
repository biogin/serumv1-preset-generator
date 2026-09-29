"""The Parameter Reference: Serum 1's parameters, as data.

Each entry names a parameter the way Serum's automation list does, says where
it lives in the preset (its VST parameter index) and how its stored 0..1 value
maps to what Serum displays.
"""

from dataclasses import dataclass
from enum import Enum


class Scale(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    OPTIONS = "options"


@dataclass(frozen=True)
class Parameter:
    name: str
    index: int
    scale: Scale
    minimum: float = 0.0
    maximum: float = 1.0
    unit: str = ""
    options: tuple[str, ...] = ()
    # Option menus are stored as index / divisor. Serum builds that had fewer
    # options used smaller divisors, so older presets need a different one.
    # The first divisor is the current build's (len(options) - 1).
    legacy_divisors: tuple[int, ...] = ()


FILTER_TYPES = (
    "MG Low 6", "MG Low 12", "MG Low 18", "MG Low 24",
    "Low 6", "Low 12", "Low 18", "Low 24",
    "High 6", "High 12", "High 18", "High 24",
    "Band 12", "Band 24", "Peak 12", "Peak 24", "Notch 12", "Notch 24",
    "LH 6", "LH 12", "LB 12", "LP 12", "LN 12", "HB 12", "HP 12", "HN 12",
    "BP 12", "BN 12", "PP 12", "PN 12", "NN 12",
    "L/B/H 12", "L/B/H 24", "L/P/H 12", "L/P/H 24", "L/N/H 12", "L/N/H 24",
    "B/P/N 12", "B/P/N 24",
    "Cmb +", "Cmb -", "Cmb L6+", "Cmb L6-", "Cmb H6+", "Cmb H6-", "Cmb HL6+", "Cmb HL6-",
    "Flg +", "Flg -", "Flg L6+", "Flg L6-", "Flg H6+", "Flg H6-", "Flg HL6+", "Flg HL6-",
    "Phs 12+", "Phs 12-", "Phs 24+", "Phs 24-", "Phs 36+", "Phs 36-", "Phs 48+", "Phs 48-",
    "Phs 48L6+", "Phs 48L6-", "Phs 48H6+", "Phs 48H6-", "Phs 48HL6+", "Phs 48HL6-",
    "FPhs 12HL6+", "FPhs 12HL6-",
    "Low EQ 6", "Low EQ 12", "Band EQ 12", "High EQ 6", "High EQ 12",
    "Ring Mod", "Ring Modx2", "SampHold", "SampHold-", "Combs", "Allpasses", "Reverb",
    "French LP", "German LP", "Add Bass", "Formant-I", "Formant-II", "Formant-III",
    "Bandreject", "Dist.Comb 1 LP", "Dist.Comb 1 BP", "Dist.Comb 2 LP", "Dist.Comb 2 BP",
    "Scream LP", "Scream BP",
)  # fmt: skip

PARAMETERS: tuple[Parameter, ...] = (
    Parameter("MasterVol", 0, Scale.LINEAR, 0.0, 100.0, "%"),
    Parameter("A Vol", 1, Scale.LINEAR, 0.0, 100.0, "%"),
    Parameter("Fil Type", 44, Scale.OPTIONS, options=FILTER_TYPES, legacy_divisors=(89, 88)),
    # MIDI note 0 (8.18 Hz) to 22.05 kHz; fits Serum's own read-out within display rounding.
    Parameter("Fil Cutoff", 45, Scale.EXPONENTIAL, 440 * 2 ** (-69 / 12), 22050.0, "Hz"),
    Parameter("Fil Reso", 46, Scale.LINEAR, 0.0, 100.0, "%"),
)

PARAMETERS_BY_NAME: dict[str, Parameter] = {p.name: p for p in PARAMETERS}
