"""
Tests for the top-level `binaries:` config section (issue #42).

Binaries are loaded during ``System.__init__`` before reset, so the bytes
are observable via ``System.peek``. Coverage validation lives in the
loader (Rule 13); construction trusts the config.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from py6502.sim.system import (
    BinarySource,
    ConfigError,
    CpuSpec,
    MemoryRegion,
    System,
    SystemConfig,
)
from py6502.sim.system.loader import from_yaml_text


def _base_yaml(
    *,
    memory: str,
    binaries: str,
) -> str:
    return f"""
version: 1
id: bintest
name: BinTest
description: binaries test fixture
cpu:
  type: MOS6502
  hz: 1000000
memory:
{memory}
binaries:
{binaries}
"""


def _write_bin(tmp_path: Path, name: str, size: int, fill: int = 0xAB) -> Path:
    target = tmp_path / name
    target.write_bytes(bytes([fill]) * size)
    return target


def test_binary_loads_into_single_region(tmp_path: Path) -> None:
    path = _write_bin(tmp_path, "prog.bin", 0x10, fill=0x5A)
    text = _base_yaml(
        memory="  - { name: RAM, start: 0x0000, size: 0x1000 }",
        binaries=f"  - {{ source: 'file:{path}', address: 0x0100 }}",
    )
    config = from_yaml_text(text, base_dir=tmp_path)
    system = System(config, base_dir=tmp_path)
    assert system.peek(0x0100) == 0x5A
    assert system.peek(0x010F) == 0x5A
    # Neighbours untouched.
    assert system.peek(0x00FF) == 0x00
    assert system.peek(0x0110) == 0x00


def test_binary_spans_two_contiguous_regions(tmp_path: Path) -> None:
    # RAM 0x0000-0x0FFF and ROM 0x1000-0x10FF are adjacent; a 0x100-byte
    # binary at 0x0F80 crosses the boundary: the first 0x80 bytes land
    # in RAM, the next 0x80 in ROM.
    data = bytes(i & 0xFF for i in range(0x100))
    target = tmp_path / "span.bin"
    target.write_bytes(data)
    text = _base_yaml(
        memory=(
            "  - { name: RAM, start: 0x0000, size: 0x1000 }\n"
            "  - { name: ROM, start: 0x1000, size: 0x0100, read_only: true }"
        ),
        binaries=f"  - {{ source: 'file:{target}', address: 0x0F80 }}",
    )
    config = from_yaml_text(text, base_dir=tmp_path)
    system = System(config, base_dir=tmp_path)
    # First byte of the binary lands at 0x0F80 in RAM.
    assert system.peek(0x0F80) == data[0]
    # The byte straddling the boundary is exactly at 0x1000 (ROM start).
    assert system.peek(0x1000) == data[0x1000 - 0x0F80]
    # Final byte lands near the end of ROM.
    assert system.peek(0x0F80 + 0x100 - 1) == data[-1]


def test_binary_outside_all_regions_rejected(tmp_path: Path) -> None:
    path = _write_bin(tmp_path, "p.bin", 0x10)
    text = _base_yaml(
        memory="  - { name: RAM, start: 0x0000, size: 0x1000 }",
        binaries=f"  - {{ source: 'file:{path}', address: 0x8000 }}",
    )
    with pytest.raises(ConfigError, match="Rule 13.*not inside any memory region"):
        from_yaml_text(text, base_dir=tmp_path)


def test_binary_extends_past_mapped_range_rejected(tmp_path: Path) -> None:
    # RAM covers 0x0000..0x0FFF. Binary at 0x0F80 of 0x100 bytes reaches
    # 0x1080, past the last mapped byte — no ROM region follows.
    path = _write_bin(tmp_path, "p.bin", 0x100)
    text = _base_yaml(
        memory="  - { name: RAM, start: 0x0000, size: 0x1000 }",
        binaries=f"  - {{ source: 'file:{path}', address: 0x0F80 }}",
    )
    with pytest.raises(ConfigError, match="Rule 13.*extends past"):
        from_yaml_text(text, base_dir=tmp_path)


def test_binary_straddling_a_gap_rejected(tmp_path: Path) -> None:
    # Regions at 0x0000-0x0FFF and 0x2000-0x20FF leave a gap;
    # a 0x200-byte binary at 0x0F80 lands inside RAM but its tail lands
    # in the gap.
    path = _write_bin(tmp_path, "p.bin", 0x200)
    text = _base_yaml(
        memory=(
            "  - { name: LO, start: 0x0000, size: 0x1000 }\n"
            "  - { name: HI, start: 0x2000, size: 0x0100 }"
        ),
        binaries=f"  - {{ source: 'file:{path}', address: 0x0F80 }}",
    )
    with pytest.raises(ConfigError, match="Rule 13.*extends past"):
        from_yaml_text(text, base_dir=tmp_path)


def test_binary_undeclared_bus_rejected(tmp_path: Path) -> None:
    # v0.1 Rule 9 fires first on any non-'main' bus name; we assert that
    # the combination still surfaces a useful error. The test documents
    # the layering even though Rule 9 preempts Rule 13 here.
    path = _write_bin(tmp_path, "p.bin", 0x10)
    text = _base_yaml(
        memory="  - { name: RAM, start: 0x0000, size: 0x1000 }",
        binaries=f"  - {{ source: 'file:{path}', address: 0x0000, bus: graphics }}",
    )
    with pytest.raises(ConfigError, match="Rule (9|13)"):
        from_yaml_text(text, base_dir=tmp_path)


def test_binary_zero_bytes_rejected(tmp_path: Path) -> None:
    path = _write_bin(tmp_path, "empty.bin", 0)
    text = _base_yaml(
        memory="  - { name: RAM, start: 0x0000, size: 0x1000 }",
        binaries=f"  - {{ source: 'file:{path}', address: 0x0000 }}",
    )
    with pytest.raises(ConfigError, match="Rule 13.*zero bytes"):
        from_yaml_text(text, base_dir=tmp_path)


def test_overlapping_binaries_rejected(tmp_path: Path) -> None:
    a = _write_bin(tmp_path, "a.bin", 0x20)
    b = _write_bin(tmp_path, "b.bin", 0x20)
    text = _base_yaml(
        memory="  - { name: RAM, start: 0x0000, size: 0x1000 }",
        binaries=(
            f"  - {{ source: 'file:{a}', address: 0x0100 }}\n"
            f"  - {{ source: 'file:{b}', address: 0x0110 }}"
        ),
    )
    with pytest.raises(ConfigError, match="Rule 13.*overlaps"):
        from_yaml_text(text, base_dir=tmp_path)


def test_binary_loads_into_read_only_region(tmp_path: Path) -> None:
    """
    A binary targeting a ``read_only: true`` region must succeed — the
    initial payload is written directly into the underlying buffer,
    bypassing the ROM guard which only applies to runtime writes.
    """
    path = _write_bin(tmp_path, "rom.bin", 0x40, fill=0xEE)
    text = _base_yaml(
        memory=(
            "  - { name: RAM, start: 0x0000, size: 0x1000 }\n"
            "  - { name: ROM, start: 0xFF00, size: 0x0100, read_only: true }"
        ),
        binaries=f"  - {{ source: 'file:{path}', address: 0xFF00 }}",
    )
    config = from_yaml_text(text, base_dir=tmp_path)
    system = System(config, base_dir=tmp_path)
    assert system.peek(0xFF00) == 0xEE
    assert system.peek(0xFF3F) == 0xEE


def test_system_config_direct_construction_load_succeeds(tmp_path: Path) -> None:
    """
    Constructing a ``SystemConfig`` directly (bypassing the loader) and
    handing it to ``System`` should still load the binary — the system
    trusts an already-validated config.
    """
    path = _write_bin(tmp_path, "p.bin", 0x08, fill=0x77)
    config = SystemConfig(
        version=1, id="direct", name="Direct", description="",
        cpu=CpuSpec(type="MOS6502", hz=1_000_000),
        memory=(MemoryRegion(name="RAM", start=0x0000, size=0x0100),),
        binaries=(BinarySource(source=f"file:{path}", address=0x0010),),
    )
    system = System(config, base_dir=tmp_path)
    assert system.peek(0x0010) == 0x77
    assert system.peek(0x0017) == 0x77
