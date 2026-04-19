"""
Unit tests for the Apple1Display + Apple1Keyboard split.

Peripheral ``read``/``write`` are ``cdef`` — not Python-callable — and
the Python surface deliberately stops at ``System``. These tests drive
the peripherals through ``System.peek`` / ``System.poke``, which is the
same path any debug panel or future test harness uses.
"""
import dataclasses
from importlib import resources

import pytest

from py6502.sim.system import CpuSpec, System, from_yaml_file


APPLE1_PRESET = resources.files("py6502.sim.assets").joinpath("presets/apple1.yaml")


@pytest.fixture
def apple1_system():
    return System.from_yaml_file(APPLE1_PRESET)


def test_keyboard_fifo_and_kbdcr_clear_on_read(apple1_system) -> None:
    assert apple1_system.send_key(ord("X"))

    assert apple1_system.peek(0xD011) == 0x80
    assert apple1_system.peek(0xD010) == (ord("X") | 0x80)
    assert apple1_system.peek(0xD011) == 0x00


def test_display_write_renders_to_framebuffer(apple1_system) -> None:
    # The RGBA buffer is only flattened from the index buffer during
    # ``sync_display`` (invoked at the end of every coarse frontend
    # call). Pokes alone don't trigger it, so we call it explicitly
    # here — the same thing the UI does automatically after
    # run_for_microseconds / step_cycle / step_instruction.
    assert apple1_system.peek(0xD012) == 0x00
    apple1_system.poke(0xD012, ord("A"))
    assert apple1_system.peek(0xD012) == 0x80

    apple1_system.sync_display()
    fb = apple1_system.get_framebuffer()
    nonzero = sum(1 for v in fb if v > 0.01)
    assert nonzero > 0, "expected the framebuffer to have non-zero pixels after DSP write"


def test_display_framebuffer_shape(apple1_system) -> None:
    # Display contract: get_framebuffer() returns a preallocated
    # buffer-protocol object of RGBA floats (see
    # ``Component.get_framebuffer`` docstring). The frontend binds a
    # DearPyGui raw texture onto this buffer, so it must stay the same
    # object for the life of the display — no per-call allocations.
    fb = apple1_system.get_framebuffer()
    assert fb is not None
    mv = memoryview(fb)
    assert mv.format == "f"
    assert len(mv) == 256 * 240 * 4
    # The buffer is owned by the peripheral; consecutive calls must
    # return the same object.
    assert apple1_system.get_framebuffer() is fb


def test_dsp_busy_timing_via_system_run_cycles() -> None:
    """
    Accuracy First contract: after a DSP write, DSP bit 7 stays busy
    for one full NTSC frame's worth of cycles — to within one
    ``run_cycles`` batch. This test locks the contract at batch
    granularity so future refactors can't silently regress it.
    """
    system = System.from_yaml_file(APPLE1_PRESET)

    assert system.peek(0xD012) == 0x00
    system.poke(0xD012, ord("A"))
    assert system.peek(0xD012) == 0x80

    system.run_cycles(16666)
    assert system.peek(0xD012) == 0x80

    system.run_cycles(1)
    assert system.peek(0xD012) == 0x00


def test_dsp_busy_timing_scales_with_cpu_hz() -> None:
    """
    The DSP busy window is derived from the configured CPU frequency at
    bind time — ``round(cpu_hz / 60)`` cycles per NTSC frame — rather
    than being baked in at 1 MHz. At 2 MHz one frame is 33 333 cycles,
    so the flag must still be busy at cycle 33 332 and cleared at 33 333.
    """
    base_config = from_yaml_file(APPLE1_PRESET)
    fast_config = dataclasses.replace(
        base_config, cpu=CpuSpec(type="MOS6502", hz=2_000_000)
    )
    system = System(fast_config)

    assert system.peek(0xD012) == 0x00
    system.poke(0xD012, ord("A"))
    assert system.peek(0xD012) == 0x80

    system.run_cycles(33332)
    assert system.peek(0xD012) == 0x80

    system.run_cycles(1)
    assert system.peek(0xD012) == 0x00
