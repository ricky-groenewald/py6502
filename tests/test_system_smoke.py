"""
Smoke test: build the Apple 1 preset end-to-end, run wozmon for a few
simulated seconds, and verify the framebuffer contains rendered
content.
"""
from importlib import resources

from py6502.sim.system import System


APPLE1_PRESET = resources.files("py6502.sim.assets").joinpath("presets/apple1.yaml")


def test_apple1_boots_and_renders() -> None:
    system = System.from_yaml_file(APPLE1_PRESET)

    # Run for ~1 second of simulated time at 1 MHz, in 60-Hz batches.
    for _ in range(60):
        system.run_for_microseconds(16667)

    fb = system.get_framebuffer()
    assert fb is not None
    assert len(fb) == 256 * 240 * 4

    # Wozmon draws a cursor as soon as reset completes, so the
    # framebuffer should not be entirely background.
    foreground_hits = sum(1 for v in fb if v > 0.5)
    assert foreground_hits > 0, "expected wozmon to render at least a cursor"

    # And the CPU should be happily running inside wozmon's ROM.
    regs = system.get_registers()
    assert 0xFF00 <= regs["PC"] <= 0xFFFF, f"unexpected PC after boot: 0x{regs['PC']:04X}"


def test_load_binary_round_trip() -> None:
    system = System.from_yaml_file(APPLE1_PRESET)
    payload = bytes([0xEA, 0xEA, 0x4C, 0x00, 0x02])  # NOP NOP JMP $0200
    system.load_binary("RAM", 0x0200, payload)

    for i, byte in enumerate(payload):
        assert system.peek(0x0200 + i) == byte
