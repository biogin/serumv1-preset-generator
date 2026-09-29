"""The Parameter Reference: all 299 Serum 1 parameters, as data.

Each Parameter has Serum's own name for it (what hosts see in automation
lists, as Serum 1.368 reports them), the module it belongs to, its VST
parameter index, and a Curve that maps the stored 0..1 value to what Serum
displays. Sources:

* names, indices, ranges: Serum's `SYParameters` listing (0xdevalias gist),
  with the names Serum 1.368 itself reports where the listing is out of date;
* curves: fitted to read-outs captured from Serum's own interface at 229 knob
  positions (btesser/serum2vital, tools/serum_display_tables.json), and
  checked against them in tests;
* defaults: whatever the Init template holds (the owner's Init preset saved
  from Serum 1.368); read it with `fxp.read`.

Parameters whose display mapping isn't known are exposed as "% of knob
travel", which is honest and still lets the model turn them.
"""

import math
from dataclasses import dataclass
from typing import Protocol


class Curve(Protocol):
    """Maps a stored 0..1 value to what Serum displays, and back."""

    def display(self, stored: float) -> float | str: ...

    def encode(self, value: float | str) -> float:
        """Stored value for `value`; raises ValueError if Serum can't show it."""
        ...

    def describe(self) -> str:
        """The allowed values, for people and for the model's prompt."""
        ...


def _number(value: float | str, what: str) -> float:
    if isinstance(value, str) or isinstance(value, bool):
        raise ValueError(f"expected a number {what}, got {value!r}")
    if math.isnan(value):
        raise ValueError(f"expected a number {what}, got NaN")
    return float(value)


def _check_range(value: float, low: float, high: float, unit: str) -> None:
    if not low <= value <= high:
        raise ValueError(f"{value:g} is outside {low:g}..{high:g} {unit}".rstrip())


@dataclass(frozen=True)
class Linear:
    low: float
    high: float
    unit: str = ""
    step: float | None = None  # e.g. 1 for octaves: displayed values snap to whole steps

    def display(self, stored: float) -> float:
        value = self.low + (self.high - self.low) * stored
        return round(value / self.step) * self.step if self.step else value

    def encode(self, value: float | str) -> float:
        v = _number(value, f"in {self.unit or 'units'}")
        _check_range(v, self.low, self.high, self.unit)
        if self.step and abs(v / self.step - round(v / self.step)) > 1e-6:
            raise ValueError(f"{v:g} is not a whole number of {self.step:g} {self.unit}")
        return (v - self.low) / (self.high - self.low)

    def describe(self) -> str:
        whole = " (whole numbers)" if self.step == 1 else ""
        return f"{self.low:g} to {self.high:g} {self.unit}".rstrip() + whole


@dataclass(frozen=True)
class Power:
    """value = low + (high - low) * stored ** exponent (envelope times, rates)."""

    high: float
    exponent: float
    unit: str
    low: float = 0.0

    def display(self, stored: float) -> float:
        return float(self.low + (self.high - self.low) * stored**self.exponent)

    def encode(self, value: float | str) -> float:
        v = _number(value, f"in {self.unit}")
        _check_range(v, self.low, self.high, self.unit)
        return float(((v - self.low) / (self.high - self.low)) ** (1 / self.exponent))

    def describe(self) -> str:
        return f"{self.low:g} to {self.high:g} {self.unit}"


@dataclass(frozen=True)
class Exponential:
    """value = low * (high / low) ** stored (frequencies)."""

    low: float
    high: float
    unit: str = "Hz"

    def display(self, stored: float) -> float:
        return float(self.low * (self.high / self.low) ** stored)

    def encode(self, value: float | str) -> float:
        v = _number(value, f"in {self.unit}")
        _check_range(v, self.low, self.high, self.unit)
        return math.log(v / self.low) / math.log(self.high / self.low)

    def describe(self) -> str:
        return f"{self.low:.0f} to {self.high:g} {self.unit}"


@dataclass(frozen=True)
class Decibels:
    """dB = factor * log10(scale * x), where x is stored (or 1 - stored if inverted).

    Silence (x = 0) displays as `floor`.
    """

    factor: float
    high: float
    floor: float = -120.0
    scale: float = 1.0
    inverted: bool = False
    unit: str = "dB"

    def display(self, stored: float) -> float:
        x = 1 - stored if self.inverted else stored
        return self.floor if x <= 0 else max(self.floor, self.factor * math.log10(self.scale * x))

    def encode(self, value: float | str) -> float:
        v = _number(value, "in dB")
        _check_range(v, self.floor, self.high, "dB")
        x = 0.0 if v <= self.floor else 10 ** (v / self.factor) / self.scale
        return 1 - x if self.inverted else x

    def describe(self) -> str:
        return f"{self.floor:g} to {self.high:g} dB"


@dataclass(frozen=True)
class MakeupGain:
    """The compressor's gain knob: dB = 20 * log10(1 + 31 * stored ** 2), 0 to 30.1 dB."""

    unit: str = "dB"

    def display(self, stored: float) -> float:
        return 20 * math.log10(1 + 31 * stored**2)

    def encode(self, value: float | str) -> float:
        v = _number(value, "in dB")
        _check_range(v, 0.0, 30.1, "dB")
        return min(1.0, math.sqrt((10 ** (v / 20) - 1) / 31))

    def describe(self) -> str:
        return "0 to 30.1 dB"


@dataclass(frozen=True)
class Options:
    """A menu, stored as index / divisor. Labels in parentheses are unlabelled slots."""

    labels: tuple[str, ...]
    # Serum builds that had fewer entries used smaller divisors, so older
    # presets need a different one. The current build's is len(labels) - 1.
    legacy_divisors: tuple[int, ...] = ()

    @property
    def choices(self) -> tuple[str, ...]:
        return tuple(label for label in self.labels if not label.startswith("("))

    def display(self, stored: float) -> str:
        current = len(self.labels) - 1
        for divisor in (current, *self.legacy_divisors):
            scaled = stored * divisor
            if abs(scaled - round(scaled)) < 1e-3:
                return self.labels[round(scaled)]
        # Between entries, Serum shows the nearest one.
        return self.labels[min(current, max(0, round(stored * current)))]

    def encode(self, value: float | str) -> float:
        if value not in self.choices:
            raise ValueError(f"{value!r} is not one of Serum's options")
        return self.labels.index(str(value)) / (len(self.labels) - 1)

    def describe(self) -> str:
        return "one of: " + ", ".join(self.choices)


@dataclass(frozen=True)
class Stepped:
    """A knob that shows labels over runs of its 229 positions (tempo-synced times)."""

    runs: tuple[tuple[str, int], ...]  # (label, first position of its run), in order
    positions: int = 229

    def display(self, stored: float) -> str:
        position = round(stored * (self.positions - 1))
        label = self.runs[0][0]
        for run_label, start in self.runs:
            if position >= start:
                label = run_label
        return label

    def encode(self, value: float | str) -> float:
        starts = [start for _, start in self.runs] + [self.positions]
        for i, (label, start) in enumerate(self.runs):
            if label == value:
                middle = (start + starts[i + 1] - 1) // 2  # well inside the run
                return middle / (self.positions - 1)
        raise ValueError(f"{value!r} is not one of Serum's options")

    def describe(self) -> str:
        return "one of: " + ", ".join(label for label, _ in self.runs)


SWITCH = Options(("Off", "On"))
KNOB = Linear(0.0, 100.0, "% of knob travel")


@dataclass(frozen=True)
class Parameter:
    name: str
    index: int
    module: str
    curve: Curve
    # The model may set it. False for modulation-matrix amounts (ticket 05)
    # and host-only controls.
    designable: bool = True

    def display(self, stored: float) -> float | str:
        return self.curve.display(stored)

    def encode(self, value: float | str) -> float:
        return self.curve.encode(value)

    @property
    def unit(self) -> str:
        return str(getattr(self.curve, "unit", ""))

    def format(self, value: float | str) -> str:
        """`value` as Serum would show it, with its unit."""
        if isinstance(value, str):
            return value
        unit = self.unit if not self.unit.startswith("(") else ""
        return f"{value:.4g} {unit}".rstrip()

    def describe(self) -> str:
        return self.curve.describe()

    def check(self, value: float | str) -> str | None:
        """A human-readable problem with `value`, or None if Serum can hold it."""
        try:
            self.curve.encode(value)
        except ValueError as e:
            return f"{self.name}: {e}"
        return None


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

WARP_MODES = (
    "Off", "Sync", "Sync 1/2 Win.", "Sync Window", "Bend +", "Bend -", "Bend +/-", "PWM",
    "Asym +", "Asym -", "Asym +/-", "Flip", "Mirror", "Remap 1", "Remap 2", "Remap 3",
    "Remap 4", "Quantize",
)  # fmt: skip
# Serum's 24th warp entry has no label; nothing in the factory library uses it.
WARP_A = Options((*WARP_MODES, "FM (from B)", "AM (from B)", "RM (from B)", "FM (Noise)",
                  "FM (Sub)", "(unused)"))  # fmt: skip
WARP_B = Options((*WARP_MODES, "FM (from A)", "AM (from A)", "RM (from A)", "FM (Noise)",
                  "FM (Sub)", "(unused)"))  # fmt: skip

DISTORTION_MODES = Options(
    ("Tube", "SoftClip", "HardClip", "Diode 1", "Diode 2", "Lin.Fold", "Sin Fold",
     "Zero-Square", "Downsample", "Asym", "Rectify", "X-Shaper", "X-Shaper (Asym)",
     "Sine Shaper", "Stomp Box", "Tape Sat."),
    legacy_divisors=(12,),
)  # fmt: skip
UNISON_STACK = Options(
    ("off", "12 (1x)", "12 (2x)", "12 (3x)", "12+7(1x)", "12+7(2x)", "12+7(3x)",
     "Center-12", "Center-24")
)  # fmt: skip
# Stored as index / 5 in every factory preset. Serum's captured menu lists only
# five names (no Triangle); this order is the sub oscillator's own. UNVERIFIED
# for "Triangle": confirm by ear/eye in Serum (see ticket 04).
SUB_SHAPES = Options(("Sine", "RoundRect", "Triangle", "Saw", "Square", "Pulse"))
EQ_TYPES = Options(("Shelf", "Peak", "LPF"))
DELAY_MODES = Options(("Normal", "Ping-Pong", "Tap->Delay"))

LFO_SYNC_RATES = Stepped(
    (("32 bar", 0), ("16 bar", 14), ("8 bar", 30), ("4 bar", 47), ("2 bar", 63), ("bar", 79),
     ("1/2", 95), ("1/4", 112), ("1/8", 128), ("1/16", 144), ("1/32", 161), ("1/64", 177),
     ("1/128", 193), ("1/256", 209), ("fast", 226))
)  # fmt: skip
DELAY_SYNC_TIMES = Stepped(
    (("fast", 0), ("1/256", 11), ("1/128", 32), ("1/64", 52), ("1/32", 73), ("1/16", 94),
     ("1/8", 115), ("1/4", 135), ("1/2", 156), ("bar", 177), ("2 bar", 197), ("4 bar", 218))
)  # fmt: skip
COMPRESSOR_RATIOS = Stepped(
    (("1:1", 0), ("1.0:1", 1), ("1.1:1", 6), ("1.2:1", 18), ("1.3:1", 29), ("1.4:1", 40),
     ("1.5:1", 52), ("1.6:1", 63), ("1.7:1", 75), ("1.8:1", 86), ("1.9:1", 97), ("2:1", 109),
     ("3:1", 152), ("4:1", 171), ("5:1", 183), ("6:1", 191), ("7:1", 196), ("8:1", 200),
     ("10:1", 206), ("16:1", 209), ("32:1", 215), ("Limit", 224))
)  # fmt: skip

PERCENT = Linear(0.0, 100.0, "%")
PAN = Linear(-50.0, 50.0)
BIPOLAR = Linear(-100.0, 100.0)
ENV_TIME = Power(32.0, 5, "s")  # 1 s at mid-travel, 32 s at the top
FX_RATE = Power(20.0, 4, "Hz")  # free-running flanger/phaser/chorus rate
CUTOFF = Exponential(440 * 2 ** (-69 / 12), 22050.0)  # MIDI note 0 (8.18 Hz) to 22.05 kHz
DEGREES = Linear(0.0, 360.0, "°")


def _oscillator(prefix: str, first: int) -> list[Parameter]:
    module = f"Osc {prefix}"

    def p(name: str, offset: int, curve: Curve) -> Parameter:
        return Parameter(f"{prefix} {name}", first + offset, module, curve)

    return [
        p("Vol", 0, PERCENT),
        p("Pan", 1, PAN),
        p("Octave", 2, Linear(-4, 4, "oct", step=1)),
        p("Semi", 3, Linear(-12, 12, "semitones", step=1)),
        p("Fine", 4, Linear(-100, 100, "cents")),
        p("Unison", 5, Linear(1, 16, "voices", step=1)),
        p("UniDet", 6, Power(1.0, 2, "(detune amount)")),
        p("UniBlend", 7, PERCENT),
        p("Warp", 8, KNOB),
        p("CoarsePit", 9, Linear(-64, 64, "semitones")),
        p("WTPos", 10, Linear(1, 256, "(wavetable frame)", step=1)),
        p("RandPhase", 11, PERCENT),
        p("Phase", 12, DEGREES),
    ]


def _envelope(n: int, first: int, sustain: Curve, hold_name: str) -> list[Parameter]:
    module = f"Env {n}"
    return [
        Parameter(f"Env{n} Atk", first, module, ENV_TIME),
        Parameter(f"Env{n} {hold_name}", first + 1, module, ENV_TIME),
        Parameter(f"Env{n} Dec", first + 2, module, ENV_TIME),
        Parameter(f"Env{n} Sus", first + 3, module, sustain),
        Parameter(f"Env{n} Rel", first + 4, module, ENV_TIME),
    ]


def _mod_slots(first_slot: int, first_index: int, count: int) -> list[Parameter]:
    out = []
    for i in range(count):
        slot = first_slot + i
        label = f"Mod {slot}" if slot < 10 else f"Mod{slot}"
        index = first_index + 2 * i
        out.append(Parameter(f"{label} amt", index, "Mod Matrix", BIPOLAR, designable=False))
        out.append(Parameter(f"{label} out", index + 1, "Mod Matrix", PERCENT, designable=False))
    return out


_P = Parameter  # short alias: the table below is long
# The design scope covers LFOs 1-4; 5-8 exist but stay at Init.
_LFO_1_4 = False
# Tempo-sync switches stay at Init: the reference describes delay times as
# note values (sync on) and FX rates in Hz (sync off), which only holds then.
_FX_ENABLES = ("Dist", "Flg", "Phs", "Cho", "Dly", "Comp", "Rev", "EQ", "FX Fil", "Hyp")
_FX_LEVEL_NAMES = ("Dist", "Flg", "Phaser", "Chorus", "Delay", "Comp", "Reverb", "DimExp",
                   "Filter", "Hyper")  # fmt: skip

_ALL: list[Parameter] = [
    _P("MasterVol", 0, "Master", PERCENT),
    *_oscillator("A", 1),
    *_oscillator("B", 14),
    _P("Noise Level", 27, "Noise", PERCENT),
    _P("Noise Pitch", 28, "Noise", PERCENT),
    _P("Noise Fine", 29, "Noise", Linear(-1, 1)),
    _P("Noise Pan", 30, "Noise", PAN),
    _P("Noise RandPhase", 31, "Noise", PERCENT),
    _P("Noise Phase", 32, "Noise", PERCENT),
    _P("Sub Osc Level", 33, "Sub", PERCENT),
    _P("Sub Osc Pan", 34, "Sub", PAN),
    *_envelope(1, 35, Decibels(40, 0.0), "Hold"),
    _P("OscA>Fil", 40, "Filter", SWITCH),
    _P("OscB>Fil", 41, "Filter", SWITCH),
    _P("OscN>Fil", 42, "Filter", SWITCH),
    _P("OscS>Fil", 43, "Filter", SWITCH),
    _P("Fil Type", 44, "Filter", Options(FILTER_TYPES, legacy_divisors=(89, 88))),
    _P("Fil Cutoff", 45, "Filter", CUTOFF),
    _P("Fil Reso", 46, "Filter", PERCENT),
    _P("Fil Driv", 47, "Filter", PERCENT),
    _P("Fil Var", 48, "Filter", PERCENT),
    _P("Fil Mix", 49, "Filter", PERCENT),
    _P("Fil Stereo", 50, "Filter", PERCENT),
    *_envelope(2, 51, PERCENT, "Hld"),
    *_envelope(3, 56, PERCENT, "Hld"),
    *(_P(f"LFO{n} Rate", 60 + n, f"LFO {n}", LFO_SYNC_RATES) for n in range(1, 5)),
    _P("PortTime", 65, "Voicing", Power(8.0, 5, "s")),
    _P("PortCurve", 66, "Voicing", BIPOLAR),
    _P("Chaos1 BPM", 67, "Chaos 1", SWITCH),
    _P("Chaos2 BPM", 68, "Chaos 2", SWITCH),
    _P("Chaos1 Rate", 69, "Chaos 1", Power(1000.0, 5, "Hz")),
    _P("Chaos2 Rate", 70, "Chaos 2", Power(1000.0, 5, "Hz")),
    *(
        _P(f"{stage} curve{n}", 71 + 3 * (n - 1) + i, f"Env {n}", PERCENT)
        for n in range(1, 4)
        for i, stage in enumerate("ADR")
    ),
    _P("Mast.Tun", 80, "Master", KNOB, designable=False),
    _P("Verb Wet", 81, "FX Reverb", PERCENT),
    _P("VerbSize", 82, "FX Reverb", PERCENT),
    _P("Decay", 83, "FX Reverb", Linear(0.8, 12.0, "s")),
    _P("VerbLoCt", 84, "FX Reverb", PERCENT),
    _P("Spin Rate", 85, "FX Reverb", KNOB),
    _P("VerbHiCt", 86, "FX Reverb", PERCENT),
    _P("Spin Depth", 87, "FX Reverb", KNOB),
    _P("EQ FrqL", 88, "FX EQ", Exponential(21.5, 20000.0)),  # Serum shows 21.5 as "22"
    _P("EQ FrqH", 89, "FX EQ", Exponential(21.5, 20000.0)),
    _P("EQ Q L", 90, "FX EQ", PERCENT),
    _P("EQ Q H", 91, "FX EQ", PERCENT),
    _P("EQ VolL", 92, "FX EQ", Linear(-24, 24, "dB")),
    _P("EQ VolH", 93, "FX EQ", Linear(-24, 24, "dB")),
    _P("EQ TypL", 94, "FX EQ", EQ_TYPES),
    _P("EQ TypH", 95, "FX EQ", EQ_TYPES),
    _P("Dist_Wet", 96, "FX Distortion", PERCENT),
    _P("Dist_Drv", 97, "FX Distortion", PERCENT),
    _P("Dist_L/B/H", 98, "FX Distortion", PERCENT),
    _P("Dist_Mode", 99, "FX Distortion", DISTORTION_MODES),
    _P("Dist_Freq", 100, "FX Distortion", Exponential(CUTOFF.low, 13290.0)),
    _P("Dist_BW", 101, "FX Distortion", KNOB),
    _P("Dist_PrePost", 102, "FX Distortion", Options(("Off", "Pre", "Post"))),  # manual p.~21
    _P("Flg_Wet", 103, "FX Flanger", PERCENT),
    _P("Flg_BPM_Sync", 104, "FX Flanger", SWITCH, designable=False),
    _P("Flg_Rate", 105, "FX Flanger", FX_RATE),
    _P("Flg_Dep", 106, "FX Flanger", PERCENT),
    _P("Flg_Feed", 107, "FX Flanger", PERCENT),
    _P("Flg_Stereo", 108, "FX Flanger", DEGREES),
    _P("Phs_Wet", 109, "FX Phaser", PERCENT),
    _P("Phs_BPM_Sync", 110, "FX Phaser", SWITCH, designable=False),
    _P("Phs_Rate", 111, "FX Phaser", FX_RATE),
    _P("Phs_Dpth", 112, "FX Phaser", PERCENT),
    _P("Phs_Frq", 113, "FX Phaser", Exponential(20.0, 18000.0)),
    _P("Phs_Feed", 114, "FX Phaser", PERCENT),
    _P("Phs_Stereo", 115, "FX Phaser", DEGREES),
    _P("Cho_Wet", 116, "FX Chorus", PERCENT),
    _P("Cho_BPM_Sync", 117, "FX Chorus", SWITCH, designable=False),
    _P("Cho_Rate", 118, "FX Chorus", FX_RATE),
    _P("Cho_Dly", 119, "FX Chorus", Power(20.0, 2, "ms")),
    _P("Cho_Dly2", 120, "FX Chorus", Power(20.0, 2, "ms")),
    _P("Cho_Dep", 121, "FX Chorus", Power(26.0, 2, "ms")),
    _P("Cho_Feed", 122, "FX Chorus", Linear(0, 95, "%")),
    _P("Cho_Filt", 123, "FX Chorus", Exponential(50.0, 20000.0)),
    _P("Dly_Wet", 124, "FX Delay", PERCENT),
    _P("Dly_Freq", 125, "FX Delay", Exponential(40.0, 18000.0)),
    _P("Dly_BW", 126, "FX Delay", Linear(0.8, 8.2)),
    _P("Dly_BPM_Sync", 127, "FX Delay", SWITCH, designable=False),
    _P("Dly_Link", 128, "FX Delay", SWITCH),
    _P("Dly_TimL", 129, "FX Delay", DELAY_SYNC_TIMES),
    _P("Dly_TimR", 130, "FX Delay", DELAY_SYNC_TIMES),
    _P("Dly_Mode", 131, "FX Delay", DELAY_MODES),
    _P("Dly_Feed", 132, "FX Delay", PERCENT),
    _P("Dly_Off L", 133, "FX Delay", KNOB),
    _P("Dly_Off R", 134, "FX Delay", KNOB),
    _P("Cmp_Thr", 135, "FX Compressor", Decibels(60, 0.0, inverted=True)),
    _P("Cmp_Rat", 136, "FX Compressor", COMPRESSOR_RATIOS),
    _P("Cmp_Att", 137, "FX Compressor", Power(1000.0, 2, "ms", low=0.1)),
    _P("Cmp_Rel", 138, "FX Compressor", Power(999.1, 2, "ms", low=0.1)),
    _P("CmpGain", 139, "FX Compressor", MakeupGain()),
    _P("CmpMBnd", 140, "FX Compressor", SWITCH),
    _P("FX Fil Wet", 141, "FX Filter", PERCENT),
    _P("FX Fil Type", 142, "FX Filter", Options(FILTER_TYPES, legacy_divisors=(89, 88))),
    _P("FX Fil Freq", 143, "FX Filter", KNOB),
    _P("FX Fil Reso", 144, "FX Filter", PERCENT),
    _P("FX Fil Drive", 145, "FX Filter", PERCENT),
    _P("FX Fil Var", 146, "FX Filter", PERCENT),
    _P("Hyp_Wet", 147, "FX Hyper/Dimension", PERCENT),
    _P("Hyp_Rate", 148, "FX Hyper/Dimension", PERCENT),
    _P("Hyp_Detune", 149, "FX Hyper/Dimension", PERCENT),
    _P("Hyp_Unison", 150, "FX Hyper/Dimension", Linear(0, 7, "voices", step=1)),
    _P("Hyp_Retrig", 151, "FX Hyper/Dimension", SWITCH),
    _P("HypDim_Size", 152, "FX Hyper/Dimension", PERCENT),
    _P("HypDim_Mix", 153, "FX Hyper/Dimension", PERCENT),
    *(_P(f"{fx} Enable", 154 + i, "FX Rack", SWITCH) for i, fx in enumerate(_FX_ENABLES)),
    _P("OscAPitchTrack", 164, "Osc A", SWITCH),
    _P("OscBPitchTrack", 165, "Osc B", SWITCH),
    _P("Bend U", 166, "Voicing", Linear(-24, 24, "semitones", step=1)),
    _P("Bend D", 167, "Voicing", Linear(-24, 24, "semitones", step=1)),
    _P("WarpOscA", 168, "Osc A", WARP_A),
    _P("WarpOscB", 169, "Osc B", WARP_B),
    _P("SubOscShape", 170, "Sub", SUB_SHAPES),
    _P("SubOscOctave", 171, "Sub", Linear(-4, 4, "oct", step=1)),
    _P("A Uni LR", 172, "Osc A", PERCENT),
    _P("B Uni LR", 173, "Osc B", PERCENT),
    _P("A Uni Warp", 174, "Osc A", BIPOLAR),
    _P("B Uni Warp", 175, "Osc B", BIPOLAR),
    _P("A Uni WTPos", 176, "Osc A", BIPOLAR),
    _P("B Uni WTPos", 177, "Osc B", BIPOLAR),
    _P("A Uni Stack", 178, "Osc A", UNISON_STACK),
    _P("B Uni Stack", 179, "Osc B", UNISON_STACK),
    *_mod_slots(1, 180, 16),
    _P("Osc A On", 212, "Osc A", SWITCH),
    _P("Osc B On", 213, "Osc B", SWITCH),
    _P("Osc N On", 214, "Noise", SWITCH),
    _P("Osc S On", 215, "Sub", SWITCH),
    _P("Filter On", 216, "Filter", SWITCH),
    _P("Mod Wheel", 217, "Master", PERCENT, designable=False),
    *(_P(f"Macro {n}", 217 + n, "Macros", PERCENT) for n in range(1, 5)),
    _P("Amp.", 222, "Master", KNOB, designable=False),
    *(_P(f"LFO{n} smooth", 222 + n, f"LFO {n}", PERCENT) for n in range(1, 5)),
    _P("Pitch Bend", 227, "Master", KNOB, designable=False),
    *_mod_slots(17, 228, 16),
    *(_P(f"LFO{n} Rate", 255 + n, f"LFO {n}", LFO_SYNC_RATES, _LFO_1_4) for n in range(5, 9)),
    *(_P(f"LFO{n} smooth", 259 + n, f"LFO {n}", PERCENT, _LFO_1_4) for n in range(5, 9)),
    _P("FX Fil Pan", 268, "FX Filter", PERCENT),
    _P("Comp_Wet", 269, "FX Compressor", PERCENT),
    _P("CompMB L", 270, "FX Compressor", Linear(0, 200, "%")),
    _P("CompMB M", 271, "FX Compressor", Linear(0, 200, "%")),
    _P("CompMB H", 272, "FX Compressor", Linear(0, 200, "%")),
    *(_P(f"LFO{n} Rise", 272 + n, f"LFO {n}", Linear(0, 4, "s"), n <= 4) for n in range(1, 9)),
    *(_P(f"LFO{n} Delay", 280 + n, f"LFO {n}", Linear(0, 4, "s"), n <= 4) for n in range(1, 9)),
    *(
        _P(f"FX {fx} Level", 289 + i, "FX Rack", Decibels(40, 12.0, scale=2.0), designable=False)
        for i, fx in enumerate(_FX_LEVEL_NAMES)
    ),  # fmt: skip
]

PARAMETERS: tuple[Parameter, ...] = tuple(sorted(_ALL, key=lambda p: p.index))
PARAMETERS_BY_NAME: dict[str, Parameter] = {p.name: p for p in PARAMETERS}
MODULES: tuple[str, ...] = tuple(dict.fromkeys(p.module for p in PARAMETERS))


def parameters_by_module() -> dict[str, list[Parameter]]:
    return {m: [p for p in PARAMETERS if p.module == m] for m in MODULES}
