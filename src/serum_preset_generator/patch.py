from dataclasses import dataclass, field


@dataclass
class Patch:
    """A Serum 1 patch in human terms: parameter values by Parameter Reference name."""

    name: str
    params: dict[str, float | str] = field(default_factory=dict)
    # Factory wavetable paths relative to Serum's Tables folder, e.g. "Analog/PWM Juno.wav".
    # None means the oscillator plays Serum's built-in default table.
    wavetable_a: str | None = None
    wavetable_b: str | None = None
