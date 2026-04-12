"""
Tests for invalid opcode handling (GH #25).

Verifies NOP mode (skip and continue) and crash mode (raises
InvalidOPCode from run_cycles).
"""
from pathlib import Path
from textwrap import dedent

import pytest

from py6502.sim.cpu.mos6502 import InvalidOPCode
from py6502.sim.system import System


MINIMAL_CONFIG = dedent("""\
    version: 1
    id: test_cpu
    name: Test CPU
    description: Minimal 64K RAM for testing.
    cpu:
      type: MOS6502
      hz: 1000000
    memory:
      - name: RAM
        start: 0x0000
        size: 0x10000
""")


def _make_system(tmp_path, pc=0x0200):
    """Build a minimal 64K-RAM system ready to execute at pc.

    After from_yaml_file, send_reset sets _current_instruction to
    load_op_code and INTERRUPT_TYPE to RESET. Clearing INTERRUPT_TYPE
    and setting PC lets the first clock() call load the opcode at pc.
    """
    config = tmp_path / "test.yaml"
    config.write_text(MINIMAL_CONFIG)
    s = System.from_yaml_file(config)
    regs = s.get_registers()
    regs["PC"] = pc
    regs["INTERRUPT_TYPE"] = 0
    s.set_registers(regs)
    return s


@pytest.fixture
def system(tmp_path):
    return _make_system(tmp_path)


def test_crash_mode_raises_on_invalid_opcode(system) -> None:
    """Default crash mode raises InvalidOPCode during run_cycles."""
    # 0x02 is an undefined 6502 opcode at 0x0200
    system.load_binary("RAM", 0x0200, bytes([0x02]))

    with pytest.raises(InvalidOPCode, match="0x02"):
        system.run_cycles(10)


def test_nop_mode_skips_invalid_opcode(system) -> None:
    """NOP mode treats invalid opcodes as 2-cycle NOPs and continues."""
    system.set_invalid_opcode_mode(0)  # NOP mode

    # 0x02 (invalid) followed by NOP NOP
    system.load_binary("RAM", 0x0200, bytes([0x02, 0xEA, 0xEA]))

    system.run_cycles(10)

    regs = system.get_registers()
    assert regs["PC"] > 0x0202, (
        f"expected PC past 0x0202, got 0x{regs['PC']:04X}"
    )


def test_crash_mode_includes_address_in_message(system) -> None:
    """Crash mode error message includes both opcode and address."""
    # JMP $0300, then invalid opcode at $0300
    system.load_binary("RAM", 0x0200, bytes([0x4C, 0x00, 0x03]))
    system.load_binary("RAM", 0x0300, bytes([0x02]))

    with pytest.raises(InvalidOPCode, match="0x0300"):
        system.run_cycles(20)
