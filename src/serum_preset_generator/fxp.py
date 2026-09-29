"""Serum 1 `.fxp` codec.

Byte layout follows btesser/serum2vital's docs/FORMATS.md, checked against the
installed factory library: a 60-byte VST2 opaque-chunk header, then a chunk of

    zlib(state)          Serum's state, compressed at level 1
    zlib(extra)          variable size (0 bytes to MBs), kept verbatim
    uint32 LE            byte length of zlib(state)

The header's size field at offset 4 holds the whole file length, and the chunk
size at 0x38 the chunk's length. Serum silently loads Init when any of these
are wrong (ADR 0001).
"""

import struct
import zlib
from dataclasses import dataclass
from functools import cache

from .parameter_reference import PARAMETERS, PARAMETERS_BY_NAME, Parameter
from .patch import Patch
from .resources import default_template

HEADER_SIZE = 0x3C
OFF_FILE_SIZE = 0x04
OFF_PROGRAM_NAME = 0x1C
PROGRAM_NAME_SIZE = 28  # the host-facing copy; may fill all 28 bytes with no NUL
OFF_CHUNK_SIZE = 0x38
STATE_COMPRESSION_LEVEL = 1
OFF_PARAMS_0_227 = 0x3460
# Serum grew past 228 parameters after the format was fixed, so 228-298 live in
# a second block. Older builds wrote less of it (or none), and left junk in the
# part they didn't use: by state size, the index from which values can't be
# trusted and Serum's defaults apply instead (FORMATS.md, checked by serum2vital
# against the plugin's own read-back).
OFF_PARAMS_228_298 = 0x4AE0
FIRST_SECOND_BLOCK_INDEX = 228
UNTRUSTED_FROM_BY_STATE_SIZE = ((21000, 228), (28000, 260), (33000, 273))  # (size, index)
OFF_WAVETABLE_A = 0x3C08
OFF_WAVETABLE_B = 0x3E08
WAVETABLE_NAME_SIZE = 512
OFF_PRESET_NAME = 0x4972
PRESET_NAME_SIZE = 32


class FxpError(ValueError):
    """The bytes are not a Serum 1 preset this codec can read."""


@dataclass
class _Container:
    header: bytes
    state: bytes  # Serum's decompressed state bytes (not a Patch)
    extra: bytes  # the second zlib stream, still compressed


def read(data: bytes) -> Patch:
    return _patch_from_state(_unpack(data).state)


def write(patch: Patch, base: bytes) -> bytes:
    """Return `base` with `patch` applied.

    Only values that differ from what `base` already holds are written, so
    everything the Patch doesn't mention (or leaves unchanged) keeps its bytes.
    """
    container = _unpack(base)
    base_patch = _patch_from_state(container.state)
    state = bytearray(container.state)
    header = bytearray(container.header)

    for name, value in patch.params.items():
        if name not in PARAMETERS_BY_NAME:
            raise FxpError(f"unknown parameter {name!r}")
        param = PARAMETERS_BY_NAME[name]
        if value != base_patch.params.get(name):
            if len(state) < _param_offset(param.index) + 4:
                raise FxpError(f"{name}: the base Preset predates this parameter")
            struct.pack_into("<f", state, _param_offset(param.index), _encode(param, value))

    if patch.name != base_patch.name:
        _put_text(state, OFF_PRESET_NAME, PRESET_NAME_SIZE, patch.name, "preset name")
        _put_text(header, OFF_PROGRAM_NAME, PROGRAM_NAME_SIZE, patch.name, "", truncate=True)

    for offset, table, base_table in (
        (OFF_WAVETABLE_A, patch.wavetable_a, base_patch.wavetable_a),
        (OFF_WAVETABLE_B, patch.wavetable_b, base_patch.wavetable_b),
    ):
        if table != base_table:
            _put_text(state, offset, WAVETABLE_NAME_SIZE, table or "", "wavetable name")

    compressed = zlib.compress(state, STATE_COMPRESSION_LEVEL)
    chunk = compressed + container.extra + struct.pack("<I", len(compressed))
    struct.pack_into(">I", header, OFF_FILE_SIZE, HEADER_SIZE + len(chunk))
    struct.pack_into(">I", header, OFF_CHUNK_SIZE, len(chunk))
    return bytes(header) + chunk


def _patch_from_state(state: bytes) -> Patch:
    return Patch(
        name=_cstring(state, OFF_PRESET_NAME, PRESET_NAME_SIZE).strip(),
        params={p.name: _display(p, _stored_or_default(state, p.index)) for p in PARAMETERS},
        wavetable_a=_cstring(state, OFF_WAVETABLE_A, WAVETABLE_NAME_SIZE) or None,
        wavetable_b=_cstring(state, OFF_WAVETABLE_B, WAVETABLE_NAME_SIZE) or None,
    )


def _unpack(data: bytes) -> _Container:
    """Validate the container and decompress Serum's state from it."""
    if data[:4] != b"CcnK" or data[8:12] != b"FPCh" or data[16:20] != b"XfsX":
        raise FxpError("not a Serum 1 opaque-chunk .fxp")
    body = data[HEADER_SIZE:]
    try:
        state_stream = zlib.decompressobj()
        state = state_stream.decompress(body)
        after_state = state_stream.unused_data
        extra_stream = zlib.decompressobj()
        extra_stream.decompress(after_state)
    except zlib.error as e:
        raise FxpError(f"state chunk is not zlib data: {e}") from e
    if len(state) < OFF_PRESET_NAME + PRESET_NAME_SIZE:
        raise FxpError(f"state is {len(state)} bytes, too short for a Serum 1 preset")
    trailer = extra_stream.unused_data
    compressed_state_size = len(body) - len(after_state)
    if trailer != struct.pack("<I", compressed_state_size):
        raise FxpError("chunk trailer doesn't match the compressed state's length")
    extra = after_state[: len(after_state) - len(trailer)]
    return _Container(header=data[:HEADER_SIZE], state=state, extra=extra)


def _param_offset(index: int) -> int:
    if index < FIRST_SECOND_BLOCK_INDEX:
        return OFF_PARAMS_0_227 + 4 * index
    return OFF_PARAMS_228_298 + 4 * (index - FIRST_SECOND_BLOCK_INDEX)


def _stored(state: bytes, index: int) -> float:
    (value,) = struct.unpack_from("<f", state, _param_offset(index))
    return float(value)


def _stored_or_default(state: bytes, index: int) -> float:
    untrusted_from = next(
        (first for size, first in UNTRUSTED_FROM_BY_STATE_SIZE if len(state) < size), None
    )
    if untrusted_from is not None and index >= untrusted_from:
        return _init_state_values()[index]
    return _stored(state, index)


@cache
def _init_state_values() -> tuple[float, ...]:
    """Serum's defaults: the stored values of the packaged Init preset (Serum 1.368)."""
    state = _unpack(default_template()).state
    return tuple(_stored(state, index) for index in range(len(PARAMETERS)))


def _display(param: Parameter, stored: float) -> float | str:
    try:
        return param.display(stored)
    except ValueError as e:
        raise FxpError(f"{param.name}: {e}") from e


def _encode(param: Parameter, value: float | str) -> float:
    try:
        return param.encode(value)
    except ValueError as e:
        raise FxpError(f"{param.name}: {e}") from e


def _put_text(
    buf: bytearray, offset: int, size: int, text: str, label: str, truncate: bool = False
) -> None:
    """Write `text` NUL-padded into a fixed-size field, or truncated to fill it."""
    try:
        encoded = text.encode("latin-1")
    except UnicodeEncodeError:
        raise FxpError(f"{label} {text!r} has characters Serum can't store") from None
    if truncate:
        encoded = encoded[:size]
    elif len(encoded) >= size:
        raise FxpError(f"{label} {text!r} is longer than Serum's {size - 1} characters")
    buf[offset : offset + size] = encoded.ljust(size, b"\0")


def _cstring(buf: bytes, offset: int, size: int) -> str:
    return buf[offset : offset + size].split(b"\0", 1)[0].decode("latin-1")
