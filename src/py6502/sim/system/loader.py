"""
YAML → SystemConfig loader + source-URI resolver.

Parses, validates, and converts a system-config YAML file into the
frozen ``SystemConfig`` dataclass tree. Validation follows
docs/SYSTEM_CONFIG.md §7 in the order listed there; the first failing
rule raises ``ConfigError`` with a human-readable message.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from py6502.sim.system.config import (
    BusSpec,
    ComponentSpec,
    ConfigError,
    CpuSpec,
    MemoryRegion,
    SystemConfig,
)
from py6502.sim.system.registry import COMPONENT_REGISTRY


SUPPORTED_SCHEMA_VERSIONS = (1,)

_TOP_LEVEL_REQUIRED = {"version", "id", "name", "description", "cpu", "memory"}
_TOP_LEVEL_OPTIONAL = {"buses", "display", "inputs", "audio", "other", "author", "tags"}
_TOP_LEVEL_ALLOWED = _TOP_LEVEL_REQUIRED | _TOP_LEVEL_OPTIONAL

_CPU_REQUIRED = {"type", "hz"}
_BUS_ALLOWED = {"address_width"}
_MEMORY_REQUIRED = {"name", "start", "size"}
_MEMORY_ALLOWED = _MEMORY_REQUIRED | {"read_only", "bus", "source", "load_offset"}
_COMPONENT_REQUIRED = {"type", "address"}
_COMPONENT_ALLOWED = _COMPONENT_REQUIRED | {"bus", "params"}


def from_yaml_file(path: str | Path) -> SystemConfig:
    """Load a system config from a YAML file on disk."""
    path = Path(path)
    text = path.read_text()
    return from_yaml_text(text, base_dir=path.parent)


def from_yaml_text(text: str, base_dir: Path) -> SystemConfig:
    """
    Parse ``text`` as YAML, validate it, and return a ``SystemConfig``.

    ``base_dir`` is the directory used to resolve ``file:`` URIs on
    memory regions.
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parse error: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Top-level YAML must be a mapping")

    # Rule 1: schema version
    version = raw.get("version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(str(v) for v in SUPPORTED_SCHEMA_VERSIONS)
        raise ConfigError(
            f"Rule 1: unsupported schema version {version!r}. Supported: {supported}"
        )

    # Rule 2: required top-level fields
    missing = _TOP_LEVEL_REQUIRED - raw.keys()
    if missing:
        raise ConfigError(
            f"Rule 2: missing required top-level fields: {sorted(missing)}"
        )

    # Rule 3: no unknown top-level fields
    unknown = raw.keys() - _TOP_LEVEL_ALLOWED
    if unknown:
        raise ConfigError(
            f"Rule 3: unknown top-level fields: {sorted(unknown)}"
        )

    cpu = _parse_cpu(raw["cpu"])
    buses = _parse_buses(raw.get("buses"))
    memory = _parse_memory(raw["memory"])
    display = _parse_component(raw.get("display"), "display") if raw.get("display") else None
    inputs = tuple(_parse_component(item, f"inputs[{i}]") for i, item in enumerate(raw.get("inputs") or ()))
    audio = _parse_component(raw.get("audio"), "audio") if raw.get("audio") else None
    other = tuple(_parse_component(item, f"other[{i}]") for i, item in enumerate(raw.get("other") or ()))

    # Rule 4: component types exist
    _require_registered(cpu.type, "cpu.type")
    for region_ix, _region in enumerate(memory):
        pass  # Memory has no 'type' field in YAML — always the built-in Memory class.
    if display is not None:
        _require_registered(display.type, "display.type")
    for i, spec in enumerate(inputs):
        _require_registered(spec.type, f"inputs[{i}].type")
    if audio is not None:
        _require_registered(audio.type, "audio.type")
    for i, spec in enumerate(other):
        _require_registered(spec.type, f"other[{i}].type")

    # Rule 5: memory region names unique
    names_seen: set[str] = set()
    for region in memory:
        if region.name in names_seen:
            raise ConfigError(f"Rule 5: duplicate memory region name {region.name!r}")
        names_seen.add(region.name)

    # Rule 9: v0.1 only allows the 'main' bus (enforced before overlap checks).
    bad_buses = [name for name in buses if name != "main"]
    if bad_buses:
        raise ConfigError(
            f"Rule 9: bus {bad_buses[0]!r} is not supported in schema version 1 — only 'main'"
        )
    for region in memory:
        if region.bus != "main":
            raise ConfigError(
                f"Rule 9: memory region {region.name!r} references bus {region.bus!r}, only 'main' is supported"
            )
    for spec, label in _iter_component_specs(display, inputs, audio, other):
        if spec.bus != "main":
            raise ConfigError(
                f"Rule 9: {label} references bus {spec.bus!r}, only 'main' is supported"
            )

    address_width = buses["main"].address_width
    bus_max = 1 << address_width

    # Rule 8: addresses fit the bus (checked per-region before overlap detection)
    for region in memory:
        if region.start + region.size > bus_max:
            raise ConfigError(
                f"Rule 8: memory region {region.name!r} (0x{region.start:04X}+0x{region.size:04X}) "
                f"exceeds bus address width ({address_width} bits)"
            )

    # Rule 6: regions don't overlap on the same bus
    occupied: list[tuple[int, int, str]] = []
    for region in memory:
        lo = region.start
        hi = region.start + region.size - 1
        for existing_lo, existing_hi, existing_name in occupied:
            if lo <= existing_hi and existing_lo <= hi:
                raise ConfigError(
                    f"Rule 6: memory region {region.name!r} (0x{lo:04X}..0x{hi:04X}) "
                    f"overlaps with {existing_name!r} (0x{existing_lo:04X}..0x{existing_hi:04X})"
                )
        occupied.append((lo, hi, region.name))

    # Rules 7 + 8 for components: size comes from the class at wiring time.
    # The loader can't compute exact overlap without instantiating the
    # class, so the final overlap check is performed inside
    # BusController.add_component. We do validate that the component's
    # declared address fits the bus at all (start < bus_max).
    for spec, label in _iter_component_specs(display, inputs, audio, other):
        if spec.address >= bus_max:
            raise ConfigError(
                f"Rule 8: {label} address 0x{spec.address:04X} "
                f"exceeds bus address width ({address_width} bits)"
            )

    # Rules 10 + 11: source URIs resolve and fit the region
    for region in memory:
        if region.source is None:
            continue
        data = resolve_source(region.source, base_dir)
        if len(data) + region.load_offset > region.size:
            raise ConfigError(
                f"Rule 11: source for region {region.name!r} ({len(data)} bytes at offset "
                f"0x{region.load_offset:04X}) exceeds region size 0x{region.size:04X}"
            )

    return SystemConfig(
        version=version,
        id=raw["id"],
        name=raw["name"],
        description=raw["description"],
        cpu=cpu,
        memory=memory,
        buses=buses,
        display=display,
        inputs=inputs,
        audio=audio,
        other=other,
        author=raw.get("author"),
        tags=tuple(raw.get("tags") or ()),
    )


def resolve_source(uri: str, base_dir: Path) -> bytes:
    """
    Load bytes from a source URI. See SYSTEM_CONFIG.md §4.
    """
    if uri.startswith("resource:"):
        body = uri[len("resource:"):]
        if "/" not in body:
            raise ConfigError(
                f"Rule 10: malformed resource URI {uri!r} — expected 'resource:<package>/<filename>'"
            )
        package, filename = body.split("/", 1)
        try:
            return resources.files(package).joinpath(filename).read_bytes()
        except (FileNotFoundError, ModuleNotFoundError) as exc:
            raise ConfigError(f"Rule 10: cannot resolve resource URI {uri!r}: {exc}") from exc

    raw_path = uri[len("file:"):] if uri.startswith("file:") else uri
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    if not candidate.exists():
        raise ConfigError(f"Rule 10: source file not found: {candidate}")
    return candidate.read_bytes()


def _parse_cpu(raw: Any) -> CpuSpec:
    if not isinstance(raw, dict):
        raise ConfigError("cpu block must be a mapping")
    missing = _CPU_REQUIRED - raw.keys()
    if missing:
        raise ConfigError(f"cpu missing required fields: {sorted(missing)}")
    unknown = raw.keys() - _CPU_REQUIRED
    if unknown:
        raise ConfigError(f"cpu has unknown fields: {sorted(unknown)}")
    cpu_type = raw["type"]
    hz = raw["hz"]
    if not isinstance(cpu_type, str):
        raise ConfigError("cpu.type must be a string")
    if not isinstance(hz, int) or hz <= 0:
        raise ConfigError(f"cpu.hz must be a positive integer, got {hz!r}")
    return CpuSpec(type=cpu_type, hz=hz)


def _parse_buses(raw: Any) -> dict[str, BusSpec]:
    if raw is None:
        return {"main": BusSpec()}
    if not isinstance(raw, dict):
        raise ConfigError("buses block must be a mapping")
    out: dict[str, BusSpec] = {}
    for name, entry in raw.items():
        if entry is None:
            entry = {}
        if not isinstance(entry, dict):
            raise ConfigError(f"buses.{name} must be a mapping")
        unknown = entry.keys() - _BUS_ALLOWED
        if unknown:
            raise ConfigError(f"buses.{name} has unknown fields: {sorted(unknown)}")
        width = entry.get("address_width", 16)
        if not isinstance(width, int) or width <= 0:
            raise ConfigError(f"buses.{name}.address_width must be a positive integer")
        out[name] = BusSpec(address_width=width)
    if "main" not in out:
        out["main"] = BusSpec()
    return out


def _parse_memory(raw: Any) -> tuple[MemoryRegion, ...]:
    if not isinstance(raw, list) or not raw:
        raise ConfigError("memory must be a non-empty list")
    regions: list[MemoryRegion] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ConfigError(f"memory[{i}] must be a mapping")
        missing = _MEMORY_REQUIRED - entry.keys()
        if missing:
            raise ConfigError(f"memory[{i}] missing required fields: {sorted(missing)}")
        unknown = entry.keys() - _MEMORY_ALLOWED
        if unknown:
            raise ConfigError(f"memory[{i}] has unknown fields: {sorted(unknown)}")
        name = entry["name"]
        start = entry["start"]
        size = entry["size"]
        if not isinstance(name, str):
            raise ConfigError(f"memory[{i}].name must be a string")
        if not isinstance(start, int):
            raise ConfigError(f"memory[{i}].start must be an integer")
        if not isinstance(size, int) or size <= 0:
            raise ConfigError(f"memory[{i}].size must be a positive integer")
        regions.append(
            MemoryRegion(
                name=name,
                start=start,
                size=size,
                read_only=bool(entry.get("read_only", False)),
                bus=entry.get("bus", "main"),
                source=entry.get("source"),
                load_offset=int(entry.get("load_offset", 0)),
            )
        )
    return tuple(regions)


def _parse_component(raw: Any, label: str) -> ComponentSpec:
    if not isinstance(raw, dict):
        raise ConfigError(f"{label} must be a mapping")
    missing = _COMPONENT_REQUIRED - raw.keys()
    if missing:
        raise ConfigError(f"{label} missing required fields: {sorted(missing)}")
    unknown = raw.keys() - _COMPONENT_ALLOWED
    if unknown:
        raise ConfigError(f"{label} has unknown fields: {sorted(unknown)}")
    comp_type = raw["type"]
    address = raw["address"]
    if not isinstance(comp_type, str):
        raise ConfigError(f"{label}.type must be a string")
    if not isinstance(address, int):
        raise ConfigError(f"{label}.address must be an integer")
    params = raw.get("params") or {}
    if not isinstance(params, dict):
        raise ConfigError(f"{label}.params must be a mapping")
    return ComponentSpec(
        type=comp_type,
        address=address,
        bus=raw.get("bus", "main"),
        params=params,
    )


def _require_registered(name: str, label: str) -> None:
    if name not in COMPONENT_REGISTRY:
        available = ", ".join(sorted(COMPONENT_REGISTRY))
        raise ConfigError(
            f"Rule 4: {label} references unknown type {name!r}. Available: {available}"
        )


def _iter_component_specs(display, inputs, audio, other):
    if display is not None:
        yield display, "display"
    for i, spec in enumerate(inputs):
        yield spec, f"inputs[{i}]"
    if audio is not None:
        yield audio, "audio"
    for i, spec in enumerate(other):
        yield spec, f"other[{i}]"
