"""
Unit tests for the YAML → SystemConfig loader.
"""
from importlib import resources
from pathlib import Path

import pytest

from py6502.sim.system import ConfigError, SystemConfig, from_yaml_file
from py6502.sim.system.loader import from_yaml_text


APPLE1_PRESET = Path(
    str(resources.files("py6502.sim.assets").joinpath("presets/apple1.yaml"))
)


def test_apple1_preset_round_trip() -> None:
    config = from_yaml_file(APPLE1_PRESET)
    assert isinstance(config, SystemConfig)
    assert config.version == 1
    assert config.id == "apple_i"
    assert config.cpu.type == "MOS6502"
    assert config.cpu.hz == 1_000_000
    assert len(config.memory) == 2
    region_by_name = {region.name: region for region in config.memory}
    assert region_by_name["RAM"].start == 0x0000
    assert region_by_name["RAM"].size == 0x1000
    assert region_by_name["RAM"].read_only is False
    assert region_by_name["ROM"].read_only is True
    assert len(config.binaries) == 1
    assert config.binaries[0].address == 0xFF00
    assert config.binaries[0].source.startswith("resource:")
    assert config.display is not None
    assert config.display.type == "Apple1Display"
    assert config.display.address == 0xD012
    assert len(config.inputs) == 1
    assert config.inputs[0].type == "Apple1Keyboard"
    assert config.inputs[0].address == 0xD010


def test_missing_required_field_fails_rule_2(tmp_path: Path) -> None:
    text = """
version: 1
id: no_name_field
description: bad
cpu:
  type: MOS6502
  hz: 1000000
memory:
  - name: RAM
    start: 0
    size: 16
"""
    with pytest.raises(ConfigError, match="Rule 2"):
        from_yaml_text(text, base_dir=tmp_path)


def test_unknown_top_level_field_fails_rule_3(tmp_path: Path) -> None:
    text = """
version: 1
id: extras
name: Extras
description: extras
extra_top_level: true
cpu:
  type: MOS6502
  hz: 1000000
memory:
  - name: RAM
    start: 0
    size: 16
"""
    with pytest.raises(ConfigError, match="Rule 3"):
        from_yaml_text(text, base_dir=tmp_path)


def test_unknown_component_type_fails_rule_4(tmp_path: Path) -> None:
    text = """
version: 1
id: bad_type
name: Bad
description: bad
cpu:
  type: MOS9999
  hz: 1000000
memory:
  - name: RAM
    start: 0
    size: 16
"""
    with pytest.raises(ConfigError, match="Rule 4"):
        from_yaml_text(text, base_dir=tmp_path)


def test_duplicate_region_name_fails_rule_5(tmp_path: Path) -> None:
    text = """
version: 1
id: dup_region
name: Dup
description: dup
cpu:
  type: MOS6502
  hz: 1000000
memory:
  - name: RAM
    start: 0
    size: 16
  - name: RAM
    start: 0x100
    size: 16
"""
    with pytest.raises(ConfigError, match="Rule 5"):
        from_yaml_text(text, base_dir=tmp_path)


def test_overlapping_memory_regions_fails_rule_6(tmp_path: Path) -> None:
    text = """
version: 1
id: overlap
name: Overlap
description: overlap
cpu:
  type: MOS6502
  hz: 1000000
memory:
  - name: RAM
    start: 0x0000
    size: 0x2000
  - name: ROM
    start: 0x1800
    size: 0x1000
"""
    with pytest.raises(ConfigError, match="Rule 6"):
        from_yaml_text(text, base_dir=tmp_path)


def test_unsupported_bus_fails_rule_9(tmp_path: Path) -> None:
    text = """
version: 1
id: multi_bus
name: Multi
description: multi
cpu:
  type: MOS6502
  hz: 1000000
buses:
  main:
    address_width: 16
  ppu:
    address_width: 14
memory:
  - name: RAM
    start: 0
    size: 16
"""
    with pytest.raises(ConfigError, match="Rule 9"):
        from_yaml_text(text, base_dir=tmp_path)


def test_region_exceeds_bus_fails_rule_8(tmp_path: Path) -> None:
    text = """
version: 1
id: too_big
name: Big
description: big
cpu:
  type: MOS6502
  hz: 1000000
memory:
  - name: RAM
    start: 0xFF00
    size: 0x0200
"""
    with pytest.raises(ConfigError, match="Rule 8"):
        from_yaml_text(text, base_dir=tmp_path)


def test_per_region_source_rejected_post_42(tmp_path: Path) -> None:
    """
    #42 moved binary sources to a top-level `binaries:` section. The old
    per-region `source` / `load_offset` fields must now fail Rule 3 as
    unknown fields — a clean break, no silent migration.
    """
    text = """
version: 1
id: legacy_source
name: Legacy
description: legacy
cpu:
  type: MOS6502
  hz: 1000000
memory:
  - name: ROM
    start: 0xFF00
    size: 0x0100
    source: resource:py6502.sim.assets.bios/apple1-wozmon.bin
"""
    with pytest.raises(ConfigError, match="memory\\[0\\] has unknown fields"):
        from_yaml_text(text, base_dir=tmp_path)


def test_schema_version_zero_fails_rule_1(tmp_path: Path) -> None:
    text = """
version: 999
id: v0
name: V0
description: v0
cpu:
  type: MOS6502
  hz: 1000000
memory:
  - name: RAM
    start: 0
    size: 16
"""
    with pytest.raises(ConfigError, match="Rule 1"):
        from_yaml_text(text, base_dir=tmp_path)
