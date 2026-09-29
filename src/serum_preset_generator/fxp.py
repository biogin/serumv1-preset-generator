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

from .parameter_reference import (
    LEGACY_MOD_SOURCES,
    MOD_AMOUNT_LIMIT,
    MOD_DESTINATION_MENU,
    MOD_SLOTS,
    MOD_SOURCE_IDS,
    MOD_SOURCES,
    PARAMETERS,
    PARAMETERS_BY_NAME,
    Parameter,
    mod_slot_parameters,
)
from .patch import Patch, Routing
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
# Modulation matrix: 32 records of 40 bytes. Slots 1-16 sit at the start of
# the state; 17-32 further in. Each record ends with a self-identifying marker
# 80 <slot - 1> FF at +0x21 (FORMATS.md; the slot byte is 0-based).
MOD_RECORD_SIZE = 40
MOD_FIXED_SLOTS = 16  # slots 1-16 sit at fixed offsets; 17-32 are found by marker
MOD_AMOUNTS_AT = 0x00  # float32 x3: amount on a 0..1 scale, amount (-1..1), output (0..1)
MOD_BIPOLAR_AT = 0x0C  # uint8: 1 = bipolar
MOD_ROUTE_AT = 0x14  # uint16 x4: source id, aux source id, destination menu position, index
MOD_MARKER_AT = 0x21
MOD_EMPTY_ROUTE = (0, 0, 173, 316)  # what Serum stores in an empty slot
# States this large are written by the current build (the "new layout"); older
# builds number some mod sources differently.
CURRENT_BUILD_MIN_STATE = 100_000
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

    if patch.routings is not None and patch.routings != base_patch.routings:
        _write_routings(state, patch.routings)

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
        routings=_read_routings(state),
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


def _mod_record_offsets(state: bytes | bytearray) -> list[int]:
    """Offsets of the modulation records present, in slot order."""
    offsets = []
    for slot in range(MOD_SLOTS):
        marker = bytes([0x80, slot, 0xFF])
        if slot < MOD_FIXED_SLOTS:
            fixed = slot * MOD_RECORD_SIZE
            at = fixed + MOD_MARKER_AT
            found = fixed if state[at : at + 3] == marker else -1
        else:
            at = state.find(marker, MOD_FIXED_SLOTS * MOD_RECORD_SIZE)
            found = at - MOD_MARKER_AT if at != -1 else -1
        if found == -1:
            break
        offsets.append(found)
    return offsets


def _is_current_build(state: bytes | bytearray) -> bool:
    return len(state) >= CURRENT_BUILD_MIN_STATE


def _read_routings(state: bytes) -> list[Routing]:
    sources = MOD_SOURCES if _is_current_build(state) else LEGACY_MOD_SOURCES
    routings = []
    for slot, offset in enumerate(_mod_record_offsets(state), start=1):
        source, _aux, _menu, destination = struct.unpack_from("<HHHH", state, offset + MOD_ROUTE_AT)
        if source == 0:
            continue
        _, amount, _ = struct.unpack_from("<fff", state, offset + MOD_AMOUNTS_AT)
        routings.append(
            Routing(
                source=sources.get(source, f"Source {source} (older Serum build)"),
                destination=(
                    PARAMETERS[destination].name
                    if destination < len(PARAMETERS)
                    else f"Parameter {destination}"
                ),
                amount=round(amount * 100, 4),
                bipolar=state[offset + MOD_BIPOLAR_AT] == 1,
                slot=slot,
            )
        )
    return routings


def _write_routings(state: bytearray, routings: list[Routing]) -> None:
    if not _is_current_build(state):
        raise FxpError(
            "routings can only be written onto a Preset saved by the current build, "
            "not an older Serum build (it numbers sources differently)"
        )
    offsets = _mod_record_offsets(state)
    if len(routings) > len(offsets):
        raise FxpError(f"{len(routings)} routings, but the base Preset has {len(offsets)} slots")
    for slot, offset in enumerate(offsets, start=1):
        if slot <= len(routings):
            routing = routings[slot - 1]
            route = (*_route_ids(slot, routing),)
            amount, bipolar = routing.amount / 100, routing.bipolar
        else:
            route, amount, bipolar = MOD_EMPTY_ROUTE, 0.0, False
        # The first float mirrors the amount on a 0..1 scale (0.5 in empty slots).
        struct.pack_into("<fff", state, offset + MOD_AMOUNTS_AT, (amount + 1) / 2, amount, 1.0)
        state[offset + MOD_BIPOLAR_AT] = 1 if bipolar else 0
        struct.pack_into("<HHHH", state, offset + MOD_ROUTE_AT, *route)
        # The slot's amount and output knobs are also parameters.
        amount_param, output_param = mod_slot_parameters(slot)
        struct.pack_into(
            "<f", state, _param_offset(amount_param.index), amount_param.encode(amount * 100)
        )
        struct.pack_into("<f", state, _param_offset(output_param.index), output_param.encode(100.0))


def _route_ids(slot: int, routing: Routing) -> tuple[int, int, int, int]:
    """(source id, aux source id, destination menu position, destination index)."""
    source = MOD_SOURCE_IDS.get(routing.source)
    if source is None:
        raise FxpError(f"routing {slot}: {routing.source!r} is not a Serum modulation source")
    param = PARAMETERS_BY_NAME.get(routing.destination)
    if param is None or param.index not in MOD_DESTINATION_MENU:
        raise FxpError(f"routing {slot}: {routing.destination!r} is not a writable destination")
    if abs(routing.amount) > MOD_AMOUNT_LIMIT:
        raise FxpError(f"routing {slot}: amount {routing.amount:g} is outside -100..100 %")
    return source, 0, MOD_DESTINATION_MENU[param.index], param.index


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
