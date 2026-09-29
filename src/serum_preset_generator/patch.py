from dataclasses import dataclass, field


@dataclass(frozen=True)
class Routing:
    """One modulation-matrix slot: `source` moves `destination` by `amount` percent."""

    source: str  # e.g. "LFO 1", "Env 2", "Macro 1"
    destination: str  # a Parameter Reference name, e.g. "Fil Cutoff"
    amount: float  # -100..100 %
    bipolar: bool = False  # Serum's bipolar switch: modulates around the knob
    # The matrix slot it was read from (1-32); None for routings not yet written.
    # Writing fills slots in list order.
    slot: int | None = field(default=None, compare=False)


@dataclass
class Patch:
    """A Serum 1 patch in human terms: parameter values by Parameter Reference name."""

    name: str
    params: dict[str, float | str] = field(default_factory=dict)
    # Factory wavetable paths relative to Serum's Tables folder, e.g. "Analog/PWM Juno.wav".
    # None means the oscillator plays Serum's built-in default table.
    wavetable_a: str | None = None
    wavetable_b: str | None = None
    # The modulation matrix in slot order. When writing, None keeps the base
    # Preset's routings; a list (even empty) replaces them.
    routings: list[Routing] | None = None
