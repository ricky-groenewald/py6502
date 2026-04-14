"""Round-trip tests for the SystemConfig YAML writer."""
from pathlib import Path

from py6502.sim.system import (
    ComponentSpec,
    CpuSpec,
    MemoryRegion,
    SystemConfig,
    to_yaml_text,
    write_yaml_file,
)
from py6502.sim.system.loader import from_yaml_text


BASE = Path(".")


def _minimal() -> SystemConfig:
    return SystemConfig(
        version=1,
        id="my_system",
        name="My System",
        description="A hand-rolled test system",
        cpu=CpuSpec(type="MOS6502", hz=1_000_000),
        memory=(
            MemoryRegion(name="RAM", start=0x0000, size=0x1000),
        ),
    )


def _full() -> SystemConfig:
    return SystemConfig(
        version=1,
        id="full_system",
        name="Full System",
        description="Every optional field exercised",
        cpu=CpuSpec(type="MOS6502", hz=2_000_000),
        memory=(
            MemoryRegion(name="RAM", start=0x0000, size=0x2000, read_only=False),
            MemoryRegion(
                name="ROM", start=0xFF00, size=0x0100, read_only=True,
                source="resource:py6502.sim.assets.bios/apple1-wozmon.bin",
            ),
        ),
        display=ComponentSpec(type="Apple1Display", address=0xD012, params={"blink": True}),
        inputs=(ComponentSpec(type="Apple1Keyboard", address=0xD010),),
        author="writer tests",
        tags=("test", "synthetic"),
    )


def test_round_trip_minimal():
    original = _minimal()
    text = to_yaml_text(original)
    restored = from_yaml_text(text, base_dir=BASE)
    assert restored == original


def test_round_trip_full():
    original = _full()
    text = to_yaml_text(original)
    restored = from_yaml_text(text, base_dir=BASE)
    assert restored == original


def test_hex_fields_emit_as_hex():
    text = to_yaml_text(_full())
    assert "start: 0x0" in text
    assert "start: 0xFF00" in text
    assert "size: 0x2000" in text
    assert "address: 0xD012" in text
    assert "address: 0xD010" in text


def test_hz_emits_as_decimal():
    text = to_yaml_text(_full())
    assert "hz: 2000000" in text
    assert "hz: 0x" not in text


def test_empty_optionals_are_omitted():
    text = to_yaml_text(_minimal())
    assert "author" not in text
    assert "tags" not in text
    assert "inputs" not in text
    assert "audio" not in text
    assert "other" not in text


def test_write_yaml_file_round_trip(tmp_path):
    original = _full()
    target = tmp_path / "out.yaml"
    write_yaml_file(original, target)
    assert target.exists()
    restored = from_yaml_text(target.read_text(encoding="utf-8"), base_dir=tmp_path)
    assert restored == original
