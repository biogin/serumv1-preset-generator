"""The full Parameter Reference, exercised through the FXP codec."""

import struct
import zlib

import pytest

from serum_preset_generator import fxp
from serum_preset_generator.config import default_template
from serum_preset_generator.parameter_reference import PARAMETERS, PARAMETERS_BY_NAME
from serum_preset_generator.patch import Patch


def preset_with_stored(name: str, stored: float) -> bytes:
    """The Init template with one parameter's raw 0..1 value replaced."""
    template = default_template()
    stream = zlib.decompressobj()
    state = bytearray(stream.decompress(template[0x3C:]))
    extra_and_trailer = stream.unused_data
    index = PARAMETERS_BY_NAME[name].index
    offset = 0x3460 + 4 * index if index < 228 else 0x4AE0 + 4 * (index - 228)
    struct.pack_into("<f", state, offset, stored)
    compressed = zlib.compress(state, 1)
    chunk = compressed + extra_and_trailer[:-4] + struct.pack("<I", len(compressed))
    header = bytearray(template[:0x3C])
    struct.pack_into(">I", header, 0x04, 0x3C + len(chunk))
    struct.pack_into(">I", header, 0x38, len(chunk))
    return bytes(header) + chunk


# What Serum itself displays at knob positions 0, 57, 114, 171 and 228 of 228,
# captured from the plugin's interface, converted to the reference's units
# (e.g. envelope "31" is 31 ms = 0.031 s), with the rounding of Serum's display
# as the tolerance (e.g. whole Hz, or 2 decimals). Envelope/portamento ms
# read-outs are whole ms, so their tolerance is looser near the top.
SERUM_READOUTS = [
    ("Fil Cutoff", [8, 59, 425, 3063, 22050], 0.5),
    ("Env1 Atk", [0.0, 0.031, 1.00, 7.59, 32.0], 0.005),
    ("Env2 Rel", [0.0, 0.031, 1.00, 7.59, 32.0], 0.005),
    ("Env1 Sus", [-120, -24.1, -12.0, -5.0, 0.0], 0.05),
    ("Env2 Sus", [0.0, 25.0, 50.0, 75.0, 100.0], 0.005),
    ("A UniDet", [0.0, 0.06, 0.25, 0.56, 1.0], 0.005),
    ("Cho_Rate", [0.0, 0.08, 1.25, 6.33, 20.0], 0.005),
    ("Cho_Dly", [0.0, 1.2, 5.0, 11.2, 20.0], 0.05),
    ("Cho_Dep", [0.0, 1.6, 6.5, 14.6, 26.0], 0.05),
    ("Cho_Filt", [50, 224, 1000, 4472, 20000], 0.5),
    ("Cho_Feed", [0, 24, 48, 71, 95], 0.5),
    ("Phs_Frq", [20, 109, 600, 3286, 18000], 0.5),
    ("Phs_Rate", [0.0, 0.08, 1.25, 6.33, 20.0], 0.005),
    ("Flg_Rate", [0.0, 0.08, 1.25, 6.33, 20.0], 0.005),
    ("Dist_Freq", [8, 52, 330, 2093, 13290], 0.5),
    ("EQ FrqL", [22, 119, 656, 3623, 20000], 0.5),
    ("Cmp_Thr", [0.0, -7.5, -18.1, -36.1, -120.0], 0.05),
    ("Cmp_Att", [0.1, 62.6, 250.1, 562.5, 1000.0], 0.05),
    ("Cmp_Rel", [0.1, 62.5, 249.9, 562.0, 999.1], 0.05),
    ("CmpGain", [0.0, 9.4, 18.8, 25.3, 30.1], 0.05),
    ("PortTime", [0.0, 0.008, 0.25, 1.90, 8.0], 0.0005),
    ("A CoarsePit", [-64, -32, 0, 32, 64], 0.005),
    ("LFO1 Rise", [0.0, 1.0, 2.0, 3.0, 4.0], 0.05),
    ("Dly_Freq", [40, 184, 849, 3908, 18000], 0.5),
    ("Dly_BW", [0.8, 2.6, 4.5, 6.4, 8.2], 0.05),
    ("Chaos1 Rate", [0.0, 0.977, 31.25, 237.305, 1000.0], 0.0005),
    ("Bend U", [-24, -12, 0, 12, 24], 0.5),
    ("A Uni WTPos", [-100, -50, 0, 50, 100], 0.5),
    ("MasterVol", [0, 25, 50, 75, 100], 0.5),
]


@pytest.mark.parametrize(("name", "readouts", "rounding"), SERUM_READOUTS)
def test_values_read_as_serum_displays_them(name, readouts, rounding):
    for position, expected in zip((0, 57, 114, 171, 228), readouts, strict=True):
        shown = fxp.read(preset_with_stored(name, position / 228)).params[name]
        # Serum shows 3-4 significant digits, so allow its display rounding.
        assert shown == pytest.approx(expected, rel=0.005, abs=rounding * 1.01), (name, position)


# Serum's own labels at chosen knob positions of tempo-synced and menu knobs.
@pytest.mark.parametrize(
    ("name", "position", "label"),
    [
        ("LFO1 Rate", 114, "1/4"),  # Serum's default
        ("LFO3 Rate", 0, "32 bar"),
        ("LFO6 Rate", 228, "fast"),
        ("Dly_TimL", 143, "1/4"),  # Serum's default, 0.625
        ("Dly_TimR", 120, "1/8"),
        ("Cmp_Rat", 171, "4:1"),  # Serum's default, 0.75
        ("Cmp_Rat", 228, "Limit"),
    ],
)
def test_synced_knobs_read_as_serums_labels(name, position, label):
    assert fxp.read(preset_with_stored(name, position / 228)).params[name] == label


def test_every_designable_parameter_round_trips_through_a_preset():
    template = default_template()
    failures = {}
    for param in PARAMETERS:
        if not param.designable:
            continue
        init_value = fxp.read(template).params[param.name]
        value = _a_different_value(param, init_value)
        written = fxp.read(fxp.write(Patch("t", {param.name: value}), base=template))
        got = written.params[param.name]
        ok = got == value if isinstance(value, str) else got == pytest.approx(value, rel=1e-3)
        others_unchanged = all(
            written.params[p.name] == fxp.read(template).params[p.name]
            for p in PARAMETERS[max(0, param.index - 1) : param.index + 2]
            if p is not param
        )
        if not (ok and others_unchanged):
            failures[param.name] = (value, got)

    assert failures == {}


def _a_different_value(param, init_value):
    labels = getattr(param.curve, "labels", None) or [
        label for label, _ in getattr(param.curve, "runs", ())
    ]
    if labels:
        return next(label for label in labels if label != init_value and label != "(unused)")
    for stored in (0.3, 0.7):
        value = param.display(stored)
        if value != init_value:
            return value
    raise AssertionError(param.name)


def test_the_init_template_holds_serums_documented_defaults():
    init = fxp.read(default_template()).params

    # Serum's own SYParameters listing, in display units.
    assert init["MasterVol"] == pytest.approx(70.0, abs=0.01)
    assert init["A Vol"] == pytest.approx(75.0, abs=0.01)
    assert init["A Unison"] == 1
    assert init["A WTPos"] == 1
    assert init["Fil Type"] == "MG Low 12"
    assert init["Fil Cutoff"] == pytest.approx(425, rel=0.01)
    assert init["Env1 Dec"] == pytest.approx(1.0, rel=0.01)  # 0.5 of travel
    assert init["Env2 Sus"] == pytest.approx(100.0)
    assert init["LFO1 Rate"] == "1/4"
    assert init["Dly_TimL"] == "1/4"
    assert init["Cmp_Rat"] == "4:1"
    assert init["Hyp_Unison"] == 4
    assert init["Osc A On"] == "On" and init["Osc B On"] == "Off"
    assert init["Filter On"] == "Off"
    assert init["Dist Enable"] == "Off"
    assert init["Bend U"] == 2 and init["Bend D"] == -2
    assert init["Mod 7 out"] == pytest.approx(100.0)
    assert init["CompMB M"] == pytest.approx(100.0)  # 270-272 in the second block
    assert init["LFO8 Delay"] == 0.0


# Raw values read by btesser/serum2vital's independent reader, shown through
# the curves checked above: this pins each parameter's position in the preset.
FACTORY_KNOWN_VALUES = {
    "Bass (Hard)/BA Angle Grinder [SN].fxp": {
        "A Unison": 5, "A UniDet": 0.117, "WarpOscA": "FM (from B)", "Sub Osc Level": 100.0,
        "Osc S On": "On", "Fil Driv": 59.2105, "Filter On": "On", "Env1 Sus": 0.0,
        "LFO1 Rate": "2 bar", "Dist Enable": "On", "Dist_Mode": "Tube", "Verb Wet": 11.0702,
        "Dly_TimL": "1/16", "Cmp_Rat": "1.7:1", "Hyp_Unison": 4, "Macro 1": 64.0351,
    },
    "Pads/PD Oddity [GS].fxp": {
        "WarpOscA": "FM (Noise)", "A Uni Stack": "Center-24", "SubOscShape": "RoundRect",
        "Sub Osc Level": 0.0, "Env1 Sus": -120.0, "Env2 Dec": 2.0814, "LFO1 Rate": "4 bar",
        "Dist_Mode": "HardClip", "Verb Wet": 50.9825, "Dly_TimL": "1/8", "Cmp_Rat": "4:1",
        "Hyp Enable": "Off", "Hyp_Unison": 2, "Macro 1": 40.9449, "Filter On": "Off",
    },
    "Seq/SQ Nu Skool Raver [ASL].fxp": {
        "A Unison": 5, "A UniDet": 0.0033, "WarpOscA": "Bend +/-", "Env2 Dec": 0.3613,
        "Fil Driv": 19.2982, "Verb Wet": 35.193, "Cmp_Rat": "2:1", "Hyp_Unison": 7,
        "Macro 1": 68.421,
    },
}  # fmt: skip


@pytest.mark.parametrize("preset", FACTORY_KNOWN_VALUES)
def test_factory_presets_read_their_known_values(read_factory, preset):
    params = read_factory(preset).params
    for name, expected in FACTORY_KNOWN_VALUES[preset].items():
        if isinstance(expected, str):
            assert params[name] == expected, name
        else:
            assert params[name] == pytest.approx(expected, rel=1e-3, abs=1e-3), name


def test_a_menu_knob_between_entries_reads_as_the_nearest_entry():
    # Serum shows a mode at every knob position, not only exactly on an entry.
    assert fxp.read(preset_with_stored("Dist_Mode", 1 / 228)).params["Dist_Mode"] == "Tube"
    assert (
        fxp.read(preset_with_stored("Dist_Mode", 0.33 / 15 + 1 / 15)).params["Dist_Mode"]
        == "SoftClip"
    )


def test_the_blank_warp_slot_is_not_a_designable_option():
    with pytest.raises(fxp.FxpError):
        fxp.write(Patch("t", {"WarpOscA": "(unused)"}), base=default_template())
