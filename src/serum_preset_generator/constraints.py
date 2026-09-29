"""Constraints a Sound Description can impose, each with a deterministic check.

Checks run against the whole Patch as Serum would load it (Init values plus the
draft, Routings included), and return human-readable problems for the model.

Serum's signal flow matters here: oscillators routed to the filter pass
through it (drive, and some filter types, distort), then everything, the sub
included, goes through the FX rack (Distortion, FX Filter, Reverb...).

Deliberately strict:
* "clean sub" means the sub oscillator (Osc S). It rejects any active
  Distortion FX, even one whose pre-filter is set to high-pass: how that
  setting treats the dry low end isn't verified. Driving only the oscillators
  routed through the filter, with the sub kept out of it, is.
* Modulating a drive counts as drive, whatever the knob's own value.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .patch import Patch

Constraint = Literal["clean_sub", "no_reverb", "no_distortion", "mono"]

# Filter types that distort or mangle whatever runs through them.
DISTORTING_FILTER_PREFIXES = ("Dist.Comb", "Scream", "SampHold", "Ring Mod")
PANS = {"A Pan": "Osc A On", "B Pan": "Osc B On", "Noise Pan": "Osc N On",
        "Sub Osc Pan": "Osc S On"}  # fmt: skip
STEREO_FX_MIXES = {"Cho": ("Cho_Wet",), "Flg": ("Flg_Wet",), "Phs": ("Phs_Wet",),
                   "Hyp": ("Hyp_Wet", "HypDim_Mix")}  # fmt: skip


def label(constraint: Constraint) -> str:
    return constraint.replace("_", " ")


def check(constraint: Constraint, patch: Patch) -> list[str]:
    """Problems with `patch` for `constraint`; an empty list means it holds."""
    return [f"{label(constraint)}: {p}" for p in CONSTRAINTS[constraint].check(_View(patch))]


class _View:
    """Read-only questions about a whole Patch that several checks ask."""

    def __init__(self, patch: Patch) -> None:
        self.params = patch.params
        self.routings = patch.routings or []

    def on(self, switch: str) -> bool:
        return self.params[switch] == "On"

    def number(self, name: str) -> float:
        return float(self.params[name])

    def modulated(self, destination: str) -> bool:
        return any(r.destination == destination and r.amount != 0 for r in self.routings)

    def driven(self, knob: str) -> bool:
        return self.number(knob) > 0 or self.modulated(knob)

    def filter_distorts(self) -> bool:
        return self.on("Filter On") and (
            self.driven("Fil Driv")
            or str(self.params["Fil Type"]).startswith(DISTORTING_FILTER_PREFIXES)
        )

    def fx_filter_distorts(self) -> bool:
        return self.on("FX Fil Enable") and (
            self.driven("FX Fil Drive")
            or str(self.params["FX Fil Type"]).startswith(DISTORTING_FILTER_PREFIXES)
        )

    def through_filter(self, *oscs: str) -> bool:
        return any(self.on(f"Osc {o} On") and self.on(f"Osc{o}>Fil") for o in oscs)


def _clean_sub(p: _View) -> list[str]:
    problems = []
    if p.on("Dist Enable"):
        problems.append(
            "the Distortion FX processes the whole output, sub included. Switch Dist Enable "
            "Off; get grit from the filter instead (Fil Driv, or a Dist.Comb/Scream type) "
            "with the sub kept out of it (OscS>Fil Off)"
        )
    if p.fx_filter_distorts():
        problems.append(
            "the FX Filter drives or distorts the whole output. Set FX Fil Drive to 0 and "
            "use a clean FX Fil Type, or switch FX Fil Enable Off"
        )
    if p.through_filter("S") and p.filter_distorts():
        problems.append(
            "the sub runs through a driven or distorting filter. Switch OscS>Fil Off so "
            "the sub bypasses it"
        )
    return problems


def _no_reverb(p: _View) -> list[str]:
    problems = []
    if p.on("Rev Enable"):
        problems.append("the Reverb FX is on. Switch Rev Enable Off")
    if p.on("Filter On") and p.params["Fil Type"] == "Reverb":
        problems.append("the filter's Reverb type adds reverb. Pick another Fil Type")
    if p.on("FX Fil Enable") and p.params["FX Fil Type"] == "Reverb":
        problems.append("the FX Filter's Reverb type adds reverb. Pick another FX Fil Type")
    return problems


def _no_distortion(p: _View) -> list[str]:
    problems = []
    if p.on("Dist Enable"):
        problems.append("the Distortion FX is on. Switch Dist Enable Off")
    if p.through_filter("A", "B", "N", "S") and p.filter_distorts():
        problems.append(
            "the filter adds distortion. Set Fil Driv to 0 (and don't modulate it), and "
            "avoid Dist.Comb, Scream, SampHold and Ring Mod filter types"
        )
    if p.fx_filter_distorts():
        problems.append(
            "the FX Filter adds distortion. Set FX Fil Drive to 0 and avoid distorting types"
        )
    return problems


def _mono(p: _View) -> list[str]:
    problems = []
    for pan, switch in PANS.items():
        if p.on(switch) and (p.number(pan) != 0 or p.modulated(pan)):
            problems.append(f"{pan} is off centre or modulated. Keep it at 0, unmodulated")
    for osc in "AB":
        if p.on(f"Osc {osc} On") and p.number(f"{osc} Unison") > 1 and p.driven(f"{osc} Uni LR"):
            problems.append(f"{osc} unison is spread in stereo. Set {osc} Uni LR to 0")
    for fx, mixes in STEREO_FX_MIXES.items():
        if p.on(f"{fx} Enable") and any(p.driven(mix) for mix in mixes):
            problems.append(f"the {fx} FX widens the stereo image. Switch {fx} Enable Off")
    if p.on("Dly Enable") and (
        p.params["Dly_Mode"] == "Ping-Pong"
        or p.params["Dly_TimL"] != p.params["Dly_TimR"]
        or p.params["Dly_Off L"] != p.params["Dly_Off R"]
    ):
        problems.append(
            "the delay differs between channels. Use Dly_Mode Normal with equal left and "
            "right times and offsets"
        )
    if p.on("Filter On") and (p.number("Fil Stereo") != 50 or p.modulated("Fil Stereo")):
        problems.append("Fil Stereo offsets the left and right cutoff. Keep it at 50")
    if p.on("FX Fil Enable") and (p.number("FX Fil Pan") != 50 or p.modulated("FX Fil Pan")):
        problems.append("FX Fil Pan offsets the FX Filter between channels. Keep it at 50")
    return problems


@dataclass(frozen=True)
class _Definition:
    meaning: str  # for the plan prompt: what it means and how descriptions say it
    check: Callable[[_View], list[str]]


CONSTRAINTS: dict[Constraint, _Definition] = {
    "clean_sub": _Definition(
        "the sub/low end must stay clean (undistorted), e.g. 'keep the sub clean'", _clean_sub
    ),
    "no_reverb": _Definition("no reverb, e.g. 'dry', 'no reverb'", _no_reverb),
    "no_distortion": _Definition(
        "no distortion or saturation at all, e.g. 'clean', 'no distortion'", _no_distortion
    ),
    "mono": _Definition("the sound must be mono, e.g. 'mono', 'for a mono bass'", _mono),
}
