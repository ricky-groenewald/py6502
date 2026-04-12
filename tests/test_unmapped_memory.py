"""
Tests for unmapped memory handling (GH #25).

Verifies open-bus mode (returns last data bus value) and crash mode
(raises UnallocatedAddressError from run_cycles). Also tests the
is_mapped() UI query.
"""
from importlib import resources

import pytest

from py6502.sim.bus.emptyaddress import UnallocatedAddressError
from py6502.sim.system import System


APPLE1_PRESET = resources.files("py6502.sim.assets").joinpath("presets/apple1.yaml")


@pytest.fixture
def system():
    return System.from_yaml_file(APPLE1_PRESET)


def test_open_bus_returns_last_bus_value(system) -> None:
    """In open-bus mode, reading unmapped memory returns the last bus value."""
    # Write a known value to mapped RAM, then read unmapped memory
    system.poke(0x0000, 0x42)
    value = system.peek(0x0000)
    assert value == 0x42

    # 0x5000 is unmapped in the Apple I preset — should return last bus value
    unmapped = system.peek(0x5000)
    assert unmapped == 0x42, (
        f"expected open-bus value 0x42, got 0x{unmapped:02X}"
    )


def test_crash_mode_raises_on_unmapped_read(system) -> None:
    """Crash mode raises UnallocatedAddressError on unmapped access."""
    system.set_unmapped_memory_mode(True)  # crash mode

    with pytest.raises(UnallocatedAddressError, match="0x5000"):
        system.peek(0x5000)


def test_crash_mode_raises_during_run_cycles(system) -> None:
    """Crash mode raises during sim execution if CPU reads unmapped memory."""
    system.set_unmapped_memory_mode(True)

    # JMP $5000 — CPU will try to fetch from unmapped address
    system.load_binary("RAM", 0x0200, bytes([0x4C, 0x00, 0x50]))
    regs = system.get_registers()
    regs["PC"] = 0x0200
    regs["INTERRUPT_TYPE"] = 0
    system.set_registers(regs)

    with pytest.raises(UnallocatedAddressError):
        system.run_cycles(100)


def test_is_mapped_returns_false_for_unmapped(system) -> None:
    """is_mapped() returns False for addresses not backed by a component."""
    assert system.is_mapped(0x0000) is True    # RAM
    assert system.is_mapped(0xFF00) is True    # ROM
    assert system.is_mapped(0xD010) is True    # Keyboard
    assert system.is_mapped(0xD012) is True    # Display
    assert system.is_mapped(0x5000) is False   # Unmapped
    assert system.is_mapped(0x8000) is False   # Unmapped


def test_open_bus_write_silently_drops(system) -> None:
    """Writing to unmapped memory in open-bus mode does not crash."""
    # Should not raise — writes are silently dropped
    system.poke(0x5000, 0xFF)
