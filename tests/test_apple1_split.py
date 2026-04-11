"""
Unit tests for the Apple1Display + Apple1Keyboard split.

Peripheral ``read``/``write`` are ``cdef`` — not Python-callable — and
the Python surface deliberately stops at ``System``. These tests drive
the peripherals through ``System.peek`` / ``System.poke``, which is the
same path any debug panel or future test harness uses.
"""
from importlib import resources

import pytest

from py6502.sim.system import System


APPLE1_PRESET = resources.files("py6502.sim.assets").joinpath("presets/apple1.yaml")


@pytest.fixture
def apple1_system():
    return System.from_yaml_file(APPLE1_PRESET)


def test_keyboard_lifo_and_kbdcr_clear_on_read(apple1_system) -> None:
    keyboard = apple1_system.inputs[0]
    assert keyboard.add_character_to_kb_buffer(ord("X"))

    assert apple1_system.peek(0xD011) == 0x80
    assert apple1_system.peek(0xD010) == (ord("X") | 0x80)
    assert apple1_system.peek(0xD011) == 0x00


def test_display_write_renders_to_framebuffer(apple1_system) -> None:
    assert apple1_system.peek(0xD013) == 0x00
    apple1_system.poke(0xD012, ord("A"))
    assert apple1_system.peek(0xD013) == 0x80

    fb = apple1_system.get_framebuffer()
    nonzero = sum(1 for v in fb if v > 0.01)
    assert nonzero > 0, "expected the framebuffer to have non-zero pixels after DSP write"


def test_display_framebuffer_shape(apple1_system) -> None:
    fb = apple1_system.get_framebuffer()
    assert isinstance(fb, list)
    assert len(fb) == 256 * 240 * 4


def test_dspcr_timing_via_system_run_cycles() -> None:
    """
    Accuracy First contract: after a DSP write, DSPCR stays busy for
    one full NTSC frame's worth of cycles — to within one
    ``run_cycles`` batch. This test locks the contract at batch
    granularity so future refactors can't silently regress it.
    """
    system = System.from_yaml_file(APPLE1_PRESET)

    assert system.peek(0xD013) == 0x00
    system.poke(0xD012, ord("A"))
    assert system.peek(0xD013) == 0x80

    system.run_cycles(16666)
    assert system.peek(0xD013) == 0x80

    system.run_cycles(1)
    assert system.peek(0xD013) == 0x00
