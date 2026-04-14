"""Tests for the preset-options schema and target-path resolver."""
from pathlib import Path

import pytest

from py6502.sim.system import ConfigError, OptionSpec, SystemConfig
from py6502.sim.system.loader import from_yaml_text


BASE = Path(".")


def _apple1(**extra_blocks) -> str:
    blocks = {
        "version": 1,
        "id": "apple_i",
        "name": "Apple I",
        "description": "test",
        "cpu": {"type": "MOS6502", "hz": 1000000},
        "memory": [
            {"name": "RAM", "start": 0x0000, "size": 0x1000},
        ],
        "display": {"type": "Apple1Display", "address": 0xD012},
        "inputs": [{"type": "Apple1Keyboard", "address": 0xD010}],
    }
    blocks.update(extra_blocks)
    import yaml
    return yaml.safe_dump(blocks, sort_keys=False)


def test_v1_preset_without_options_still_loads():
    cfg = from_yaml_text(_apple1(), base_dir=BASE)
    assert isinstance(cfg, SystemConfig)
    assert cfg.options == ()
    assert cfg.memory[0].size == 0x1000


def test_options_default_is_applied():
    opt = {
        "id": "ram_size", "label": "RAM", "kind": "enum",
        "target": "memory[RAM].size", "default": 0x2000,
        "choices": [
            {"value": 0x1000, "label": "4K"},
            {"value": 0x2000, "label": "8K"},
        ],
    }
    cfg = from_yaml_text(_apple1(options=[opt]), base_dir=BASE)
    assert len(cfg.options) == 1
    assert isinstance(cfg.options[0], OptionSpec)
    assert cfg.memory[0].size == 0x2000


def test_options_override_wins_over_default():
    opt = {
        "id": "ram_size", "label": "RAM", "kind": "enum",
        "target": "memory[RAM].size", "default": 0x1000,
        "choices": [
            {"value": 0x1000, "label": "4K"},
            {"value": 0x2000, "label": "8K"},
        ],
    }
    cfg = from_yaml_text(
        _apple1(options=[opt]),
        base_dir=BASE,
        option_values={"ram_size": 0x2000},
    )
    assert cfg.memory[0].size == 0x2000


def test_target_path_cpu_hz():
    opt = {
        "id": "clock", "label": "Clock", "kind": "int",
        "target": "cpu.hz", "default": 2000000,
    }
    cfg = from_yaml_text(_apple1(options=[opt]), base_dir=BASE)
    assert cfg.cpu.hz == 2000000


def test_target_path_component_address():
    opt = {
        "id": "kbd_addr", "label": "KBD addr", "kind": "hex",
        "target": "inputs[0].address", "default": 0xE000,
    }
    cfg = from_yaml_text(_apple1(options=[opt]), base_dir=BASE)
    assert cfg.inputs[0].address == 0xE000


def test_target_path_auto_creates_params_dict():
    opt = {
        "id": "blink", "label": "Blink", "kind": "bool",
        "target": "display.params.blink", "default": True,
    }
    cfg = from_yaml_text(_apple1(options=[opt]), base_dir=BASE)
    assert cfg.display.params == {"blink": True}


def test_unknown_region_name_fails_rule_12():
    opt = {
        "id": "ram_size", "label": "RAM", "kind": "int",
        "target": "memory[NONEXISTENT].size", "default": 0x1000,
    }
    with pytest.raises(ConfigError, match=r"Rule 12.*'ram_size'.*'NONEXISTENT'"):
        from_yaml_text(_apple1(options=[opt]), base_dir=BASE)


def test_index_out_of_range_fails_rule_12():
    opt = {
        "id": "kbd_addr", "label": "KBD addr", "kind": "hex",
        "target": "inputs[5].address", "default": 0xE000,
    }
    with pytest.raises(ConfigError, match=r"Rule 12.*'kbd_addr'.*index 5 out of range"):
        from_yaml_text(_apple1(options=[opt]), base_dir=BASE)


def test_non_mapping_intermediate_fails_rule_12():
    opt = {
        "id": "bad", "label": "Bad", "kind": "int",
        "target": "cpu.type.nested", "default": 1,
    }
    with pytest.raises(ConfigError, match=r"Rule 12.*'bad'.*not a mapping"):
        from_yaml_text(_apple1(options=[opt]), base_dir=BASE)


def test_unknown_option_id_in_values_fails():
    opt = {
        "id": "ram_size", "label": "RAM", "kind": "enum",
        "target": "memory[RAM].size", "default": 0x1000,
        "choices": [{"value": 0x1000, "label": "4K"}],
    }
    with pytest.raises(ConfigError, match=r"Rule 12.*unknown ids.*'typo'"):
        from_yaml_text(
            _apple1(options=[opt]),
            base_dir=BASE,
            option_values={"typo": 0x1000},
        )


def test_enum_value_not_in_choices_fails():
    opt = {
        "id": "ram_size", "label": "RAM", "kind": "enum",
        "target": "memory[RAM].size", "default": 0x1000,
        "choices": [{"value": 0x1000, "label": "4K"}],
    }
    with pytest.raises(ConfigError, match=r"Rule 12.*'ram_size'.*not a declared choice"):
        from_yaml_text(
            _apple1(options=[opt]),
            base_dir=BASE,
            option_values={"ram_size": 0x4000},
        )


def test_int_value_out_of_range_fails():
    opt = {
        "id": "clock", "label": "Clock", "kind": "int",
        "target": "cpu.hz", "default": 1000000,
        "min": 500000, "max": 2000000,
    }
    with pytest.raises(ConfigError, match=r"Rule 12.*'clock'.*above max"):
        from_yaml_text(
            _apple1(options=[opt]),
            base_dir=BASE,
            option_values={"clock": 5000000},
        )


def test_malformed_target_syntax_fails_at_parse():
    opt = {
        "id": "bad", "label": "Bad", "kind": "int",
        "target": "cpu..hz", "default": 1,
    }
    with pytest.raises(ConfigError, match=r"options\[0\]\.target token"):
        from_yaml_text(_apple1(options=[opt]), base_dir=BASE)


def test_duplicate_option_id_fails_at_parse():
    opt = {
        "id": "x", "label": "X", "kind": "int",
        "target": "cpu.hz", "default": 1000000,
    }
    with pytest.raises(ConfigError, match=r"duplicate option id 'x'"):
        from_yaml_text(_apple1(options=[opt, opt]), base_dir=BASE)


def test_indexed_token_as_terminal_fails():
    opt = {
        "id": "bad", "label": "Bad", "kind": "int",
        "target": "memory[RAM]", "default": 1,
    }
    with pytest.raises(ConfigError, match=r"Rule 12.*must be followed by a field name"):
        from_yaml_text(_apple1(options=[opt]), base_dir=BASE)
