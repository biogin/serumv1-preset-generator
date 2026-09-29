"""Serum 1 `.fxp` codec.

Byte layout follows btesser/serum2vital's docs/FORMATS.md: a VST2 opaque-chunk
container whose chunk holds two zlib streams and a trailer (ADR 0001). Reading
only needs the first stream, Serum's state; the rest matters when writing.
"""

import struct
import zlib

from .parameter_reference import PARAMETERS, Parameter, Scale
from .patch import Patch

HEADER_SIZE = 0x3C
# Parameters 0-227; 228-298 live in a second block that no starter parameter needs yet.
OFF_PARAMS_0_227 = 0x3460
OFF_WAVETABLE_A = 0x3C08
OFF_WAVETABLE_B = 0x3E08
WAVETABLE_NAME_SIZE = 512
OFF_PRESET_NAME = 0x4972
PRESET_NAME_SIZE = 32


class FxpError(ValueError):
    """The bytes are not a Serum 1 preset this codec can read."""


def read(data: bytes) -> Patch:
    state = _decompress_state(data)
    return Patch(
        name=_cstring(state, OFF_PRESET_NAME, PRESET_NAME_SIZE).strip(),
        params={p.name: _display(p, _stored(state, p.index)) for p in PARAMETERS},
        wavetable_a=_cstring(state, OFF_WAVETABLE_A, WAVETABLE_NAME_SIZE) or None,
        wavetable_b=_cstring(state, OFF_WAVETABLE_B, WAVETABLE_NAME_SIZE) or None,
    )


def _decompress_state(data: bytes) -> bytes:
    if data[:4] != b"CcnK" or data[8:12] != b"FPCh" or data[16:20] != b"XfsX":
        raise FxpError("not a Serum 1 opaque-chunk .fxp")
    try:
        state = zlib.decompressobj().decompress(data[HEADER_SIZE:])
    except zlib.error as e:
        raise FxpError(f"state chunk is not zlib data: {e}") from e
    if len(state) < OFF_PRESET_NAME + PRESET_NAME_SIZE:
        raise FxpError(f"state is {len(state)} bytes, too short for a Serum 1 preset")
    return state


def _stored(state: bytes, index: int) -> float:
    (value,) = struct.unpack_from("<f", state, OFF_PARAMS_0_227 + 4 * index)
    return float(value)


def _display(param: Parameter, stored: float) -> float | str:
    if param.scale is Scale.LINEAR:
        return param.minimum + (param.maximum - param.minimum) * stored
    if param.scale is Scale.EXPONENTIAL:
        return float(param.minimum * (param.maximum / param.minimum) ** stored)
    if param.scale is Scale.OPTIONS:
        return param.options[_option_index(param, stored)]
    raise NotImplementedError(param.scale)


def _option_index(param: Parameter, stored: float) -> int:
    for divisor in (len(param.options) - 1, *param.legacy_divisors):
        scaled = stored * divisor
        if abs(scaled - round(scaled)) < 1e-3:
            return round(scaled)
    raise FxpError(f"{param.name}: stored value {stored} matches no known option")


def _cstring(buf: bytes, offset: int, size: int) -> str:
    return buf[offset : offset + size].split(b"\0", 1)[0].decode("latin-1")
