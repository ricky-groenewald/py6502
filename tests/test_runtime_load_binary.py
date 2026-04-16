"""
Tests for ``System.load_binary_at`` (issue #57) — the runtime counterpart
to config-time binary loading.

Mirrors the coverage cases in ``test_binaries.py`` but exercises an
already-constructed ``System`` instead of going through the loader. Both
paths share ``validate_coverage`` in ``loader.py``, so these tests pin
the runtime side of that contract.
"""
from __future__ import annotations

import pytest

from py6502.sim.system import (
    ConfigError,
    CpuSpec,
    MemoryRegion,
    System,
    SystemConfig,
)


def _make_system(*memory: MemoryRegion) -> System:
    config = SystemConfig(
        version=1, id="rt", name="RT", description="",
        cpu=CpuSpec(type="MOS6502", hz=1_000_000),
        memory=memory,
    )
    return System(config)


def test_load_into_single_region() -> None:
    system = _make_system(MemoryRegion(name="RAM", start=0x0000, size=0x1000))
    payload = bytes(range(16))
    system.load_binary_at(0x0100, payload)
    for i, byte in enumerate(payload):
        assert system.peek(0x0100 + i) == byte
    # Neighbours untouched.
    assert system.peek(0x00FF) == 0x00
    assert system.peek(0x0110) == 0x00


def test_load_spans_two_contiguous_regions() -> None:
    system = _make_system(
        MemoryRegion(name="RAM", start=0x0000, size=0x1000),
        MemoryRegion(name="ROM", start=0x1000, size=0x0100, read_only=True),
    )
    payload = bytes(i & 0xFF for i in range(0x100))
    system.load_binary_at(0x0F80, payload)
    assert system.peek(0x0F80) == payload[0]
    assert system.peek(0x1000) == payload[0x1000 - 0x0F80]
    assert system.peek(0x0F80 + 0x100 - 1) == payload[-1]


def test_load_address_outside_any_region_rejected() -> None:
    system = _make_system(MemoryRegion(name="RAM", start=0x0000, size=0x1000))
    with pytest.raises(
        ConfigError,
        match=r"load_binary_at:.*not inside any memory region",
    ):
        system.load_binary_at(0x8000, bytes([0xEA] * 4))


def test_load_extending_past_mapped_range_rejected() -> None:
    system = _make_system(MemoryRegion(name="RAM", start=0x0000, size=0x1000))
    with pytest.raises(ConfigError, match=r"load_binary_at:.*extends past"):
        system.load_binary_at(0x0F80, bytes([0xEA] * 0x100))


def test_load_crossing_an_unmapped_gap_rejected() -> None:
    # Regions at 0x0000-0x0FFF and 0x2000-0x20FF leave a gap. A 0x400-byte
    # load at 0x0F80 starts inside RAM, tails into the HI region at 0x2000,
    # and crosses the gap between them.
    system = _make_system(
        MemoryRegion(name="LO", start=0x0000, size=0x1000),
        MemoryRegion(name="HI", start=0x2000, size=0x0100),
    )
    with pytest.raises(
        ConfigError,
        match=r"load_binary_at:.*crosses an unmapped gap",
    ):
        system.load_binary_at(0x0F80, bytes([0xEA] * 0x1100))


def test_load_zero_bytes_rejected() -> None:
    system = _make_system(MemoryRegion(name="RAM", start=0x0000, size=0x1000))
    with pytest.raises(ConfigError, match=r"load_binary_at:.*zero bytes"):
        system.load_binary_at(0x0000, b"")


def test_load_address_above_bus_width_rejected() -> None:
    system = _make_system(MemoryRegion(name="RAM", start=0x0000, size=0x1000))
    with pytest.raises(
        ConfigError,
        match=r"load_binary_at:.*outside the 16-bit bus",
    ):
        system.load_binary_at(0x10000, bytes([0xEA]))


def test_load_into_read_only_region_succeeds() -> None:
    """
    Runtime loads match config-time precedent: writing through
    ``Memory.set_data`` bypasses the ``read_only`` flag. Loading a ROM
    image at runtime is intentional, not a bug.
    """
    system = _make_system(
        MemoryRegion(name="ROM", start=0xFF00, size=0x0100, read_only=True),
    )
    payload = bytes([0xEE] * 0x10)
    system.load_binary_at(0xFF00, payload)
    assert system.peek(0xFF00) == 0xEE
    assert system.peek(0xFF0F) == 0xEE


def test_load_overwrites_previous_load() -> None:
    """Runtime overwrites are allowed — there's no binary-vs-binary overlap
    check at this layer (unlike config time)."""
    system = _make_system(MemoryRegion(name="RAM", start=0x0000, size=0x1000))
    system.load_binary_at(0x0100, bytes([0xAA] * 4))
    system.load_binary_at(0x0100, bytes([0xBB] * 4))
    assert system.peek(0x0100) == 0xBB
    assert system.peek(0x0103) == 0xBB
