"""
SystemConfig → YAML writer.

The inverse of ``loader.py`` for the subset of configs the custom-system
builder produces: no options, main bus only, everything resolved to
concrete values. Round-trips through ``from_yaml_text`` to an equal
``SystemConfig`` dataclass.

Address-like fields (``start``, ``size``, ``address``, ``load_offset``)
emit as ``0x…`` hex literals. Everything else uses YAML's default int
representer.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import yaml

from py6502.sim.system.config import SystemConfig


class _HexInt(int):
    """Marker subclass for ints that should emit as ``0x…`` in YAML output."""


class _SystemConfigDumper(yaml.SafeDumper):
    pass


def _represent_hex(dumper: yaml.Dumper, data: _HexInt) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:int", f"0x{int(data):X}")


_SystemConfigDumper.add_representer(_HexInt, _represent_hex)


def to_yaml_text(config: SystemConfig) -> str:
    """Serialize *config* to a YAML document. Inverse of ``from_yaml_text``."""
    doc: dict = {
        "version": config.version,
        "id": config.id,
        "name": config.name,
        "description": config.description,
    }
    if config.author:
        doc["author"] = config.author
    if config.tags:
        doc["tags"] = list(config.tags)

    doc["cpu"] = {"type": config.cpu.type, "hz": config.cpu.hz}

    doc["memory"] = [_region_dict(r) for r in config.memory]

    if config.display is not None:
        doc["display"] = _component_dict(config.display)
    if config.inputs:
        doc["inputs"] = [_component_dict(c) for c in config.inputs]
    if config.audio is not None:
        doc["audio"] = _component_dict(config.audio)
    if config.other:
        doc["other"] = [_component_dict(c) for c in config.other]

    return yaml.dump(doc, Dumper=_SystemConfigDumper, sort_keys=False)


def write_yaml_file(config: SystemConfig, path: str | Path) -> None:
    """Write *config* to *path* as UTF-8 YAML."""
    Path(path).write_text(to_yaml_text(config), encoding="utf-8")


def _region_dict(region) -> dict:
    out: dict = {
        "name": region.name,
        "start": _HexInt(region.start),
        "size": _HexInt(region.size),
    }
    if region.read_only:
        out["read_only"] = True
    if region.bus != "main":
        out["bus"] = region.bus
    if region.source is not None:
        out["source"] = region.source
    if region.load_offset:
        out["load_offset"] = _HexInt(region.load_offset)
    return out


def _component_dict(spec) -> dict:
    out: dict = {
        "type": spec.type,
        "address": _HexInt(spec.address),
    }
    if spec.bus != "main":
        out["bus"] = spec.bus
    if spec.params:
        out["params"] = dict(spec.params)
    return out
