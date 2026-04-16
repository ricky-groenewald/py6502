"""
YAML → SystemConfig loader + source-URI resolver.

Parses, validates, and converts a system-config YAML file into the
frozen ``SystemConfig`` dataclass tree. Validation follows
docs/SYSTEM_CONFIG.md §7 in the order listed there; the first failing
rule raises ``ConfigError`` with a human-readable message.
"""
from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from py6502.sim.system.config import (
    BinarySource,
    BusSpec,
    ComponentSpec,
    ConfigError,
    CpuSpec,
    MemoryRegion,
    OptionChoice,
    OptionSpec,
    SystemConfig,
)
from py6502.sim.system.registry import COMPONENT_REGISTRY


SUPPORTED_SCHEMA_VERSIONS = (1,)

_TOP_LEVEL_REQUIRED = {"version", "id", "name", "description", "cpu", "memory"}
_TOP_LEVEL_OPTIONAL = {"buses", "display", "inputs", "audio", "other", "binaries", "author", "tags", "options"}
_TOP_LEVEL_ALLOWED = _TOP_LEVEL_REQUIRED | _TOP_LEVEL_OPTIONAL

_CPU_REQUIRED = {"type", "hz"}
_BUS_ALLOWED = {"address_width"}
_MEMORY_REQUIRED = {"name", "start", "size"}
_MEMORY_ALLOWED = _MEMORY_REQUIRED | {"read_only", "bus"}
_COMPONENT_REQUIRED = {"type", "address"}
_COMPONENT_ALLOWED = _COMPONENT_REQUIRED | {"bus", "params"}
_BINARY_REQUIRED = {"source", "address"}
_BINARY_ALLOWED = _BINARY_REQUIRED | {"bus"}

_OPTION_REQUIRED = {"id", "label", "kind", "target", "default"}
_OPTION_ALLOWED = _OPTION_REQUIRED | {"choices", "min", "max", "description"}
_OPTION_KINDS = {"enum", "int", "hex", "bool"}
_OPTION_ID_RE = re.compile(r"^[a-z0-9_]+$")
# Matches one token in a target path: "name" or "name[key]".
# "key" may be an integer index or a region/entry name (letters, digits, underscore, hyphen).
_TARGET_TOKEN_RE = re.compile(r"^([a-z_][a-z0-9_]*)(?:\[([a-zA-Z0-9_\-]+)\])?$")


def from_yaml_file(path: str | Path) -> SystemConfig:
    """Load a system config from a YAML file on disk, applying option defaults."""
    return from_yaml_file_with_options(path, {})


def from_yaml_file_with_options(
    path: str | Path,
    option_values: dict[str, object],
) -> SystemConfig:
    """
    Load a system config from a YAML file with user-selected option values.

    Any options the preset declares but ``option_values`` does not override
    fall back to the option's declared ``default``.
    """
    path = Path(path)
    text = path.read_text()
    return from_yaml_text(text, base_dir=path.parent, option_values=option_values)


def from_yaml_text(
    text: str,
    base_dir: Path,
    option_values: dict[str, object] | None = None,
) -> SystemConfig:
    """
    Parse ``text`` as YAML, validate it, and return a ``SystemConfig``.

    ``base_dir`` is the directory used to resolve ``file:`` URIs on
    binary sources. ``option_values`` maps option ids to user-selected
    values; missing entries fall back to each option's declared default.
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

    options = _parse_options(raw.get("options"))
    _apply_options(raw, options, option_values or {})

    cpu = _parse_cpu(raw["cpu"])
    buses = _parse_buses(raw.get("buses"))
    memory = _parse_memory(raw["memory"])
    display = _parse_component(raw.get("display"), "display") if raw.get("display") else None
    inputs = tuple(_parse_component(item, f"inputs[{i}]") for i, item in enumerate(raw.get("inputs") or ()))
    audio = _parse_component(raw.get("audio"), "audio") if raw.get("audio") else None
    other = tuple(_parse_component(item, f"other[{i}]") for i, item in enumerate(raw.get("other") or ()))
    binaries = _parse_binaries(raw.get("binaries"))

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

    # Rule 13: binary sources resolve and cover a contiguous mapped range
    _validate_binaries(binaries, memory, buses, base_dir)

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
        binaries=binaries,
        author=raw.get("author"),
        tags=tuple(raw.get("tags") or ()),
        options=options,
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
            )
        )
    return tuple(regions)


def _parse_binaries(raw: Any) -> tuple[BinarySource, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ConfigError("binaries must be a list")
    out: list[BinarySource] = []
    for i, entry in enumerate(raw):
        label = f"binaries[{i}]"
        if not isinstance(entry, dict):
            raise ConfigError(f"{label} must be a mapping")
        missing = _BINARY_REQUIRED - entry.keys()
        if missing:
            raise ConfigError(f"{label} missing required fields: {sorted(missing)}")
        unknown = entry.keys() - _BINARY_ALLOWED
        if unknown:
            raise ConfigError(f"{label} has unknown fields: {sorted(unknown)}")
        source = entry["source"]
        address = entry["address"]
        if not isinstance(source, str) or not source:
            raise ConfigError(f"{label}.source must be a non-empty string")
        if not isinstance(address, int):
            raise ConfigError(f"{label}.address must be an integer")
        bus = entry.get("bus", "main")
        if not isinstance(bus, str):
            raise ConfigError(f"{label}.bus must be a string")
        out.append(BinarySource(source=source, address=address, bus=bus))
    return tuple(out)


def validate_coverage(
    memory: tuple[MemoryRegion, ...],
    bus: str,
    address: int,
    length: int,
    *,
    label: str,
) -> tuple[MemoryRegion, ...]:
    """
    Check that ``[address, address + length)`` is covered by a contiguous
    run of memory regions on ``bus``. Raises ``ConfigError`` prefixed with
    ``label`` on failure; returns the covering regions (sorted by start)
    on success. Shared by ``_validate_binaries`` at config time and
    ``System.load_binary_at`` at runtime so the two paths agree on
    wording and rules.
    """
    if length == 0:
        raise ConfigError(f"{label} is zero bytes")

    same_bus = sorted(
        (r for r in memory if r.bus == bus), key=lambda r: r.start
    )
    if not same_bus:
        raise ConfigError(
            f"{label} targets bus {bus!r} which has no memory regions"
        )

    # Merge adjacent regions into a list of [lo, hi) intervals (half-open).
    merged: list[list[int]] = []
    for r in same_bus:
        lo = r.start
        hi = r.start + r.size
        if merged and merged[-1][1] == lo:
            merged[-1][1] = hi
        else:
            merged.append([lo, hi])

    start = address
    end = start + length
    # Find the merged interval containing `start`.
    covering = None
    for lo, hi in merged:
        if lo <= start < hi:
            covering = (lo, hi)
            break
    if covering is None:
        raise ConfigError(
            f"{label} address 0x{start:04X} "
            f"is not inside any memory region on bus {bus!r}"
        )
    cov_lo, cov_hi = covering
    if end > cov_hi:
        # Distinguish "extends past end" from "crosses a gap".
        tail_inside = any(lo <= end - 1 < hi for lo, hi in merged)
        if tail_inside and end - 1 >= cov_hi:
            raise ConfigError(
                f"{label} "
                f"(0x{length:X} bytes at 0x{start:04X}) crosses an unmapped gap "
                f"on bus {bus!r}"
            )
        raise ConfigError(
            f"{label} "
            f"(0x{length:X} bytes at 0x{start:04X}) extends past the end of "
            f"mapped range 0x{cov_lo:04X}..0x{cov_hi - 1:04X} on bus {bus!r}"
        )

    return regions_covering(memory, bus, address, length)


def _validate_binaries(
    binaries: tuple[BinarySource, ...],
    memory: tuple[MemoryRegion, ...],
    buses: dict[str, BusSpec],
    base_dir: Path,
) -> None:
    """
    Rule 13: each binary source must resolve, be non-empty, and cover a
    contiguous mapped range on its declared bus. Binaries may not overlap.
    """
    placed: list[tuple[int, int, int]] = []  # (address, end_exclusive, index)
    for i, bs in enumerate(binaries):
        label = f"binaries[{i}]"
        if bs.bus not in buses:
            declared = ", ".join(sorted(buses))
            raise ConfigError(
                f"Rule 13: {label} references undeclared bus {bs.bus!r}. Declared: [{declared}]"
            )
        data = resolve_source(bs.source, base_dir)  # raises Rule 10 on failure
        validate_coverage(
            memory,
            bs.bus,
            bs.address,
            len(data),
            label=f"Rule 13: {label} source {bs.source!r}",
        )

        start = bs.address
        end = start + len(data)
        # Overlap between binaries on the same bus.
        for other_start, other_end, other_idx in placed:
            if start < other_end and other_start < end:
                raise ConfigError(
                    f"Rule 13: {label} range 0x{start:04X}..0x{end - 1:04X} "
                    f"overlaps with binaries[{other_idx}] on bus {bs.bus!r}"
                )
        placed.append((start, end, i))


def regions_covering(
    memory: tuple[MemoryRegion, ...],
    bus: str,
    address: int,
    length: int,
) -> tuple[MemoryRegion, ...]:
    """
    Return regions on ``bus`` whose range intersects
    ``[address, address + length)``, sorted by ``start``. Shared by the
    validator and ``System.__init__`` so both agree on the coverage set.
    """
    end = address + length
    hits = [
        r for r in memory
        if r.bus == bus and r.start < end and address < r.start + r.size
    ]
    hits.sort(key=lambda r: r.start)
    return tuple(hits)


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


def _parse_options(raw: Any) -> tuple[OptionSpec, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ConfigError("options must be a list")

    seen_ids: set[str] = set()
    out: list[OptionSpec] = []
    for i, entry in enumerate(raw):
        label_for_err = f"options[{i}]"
        if not isinstance(entry, dict):
            raise ConfigError(f"{label_for_err} must be a mapping")
        missing = _OPTION_REQUIRED - entry.keys()
        if missing:
            raise ConfigError(f"{label_for_err} missing required fields: {sorted(missing)}")
        unknown = entry.keys() - _OPTION_ALLOWED
        if unknown:
            raise ConfigError(f"{label_for_err} has unknown fields: {sorted(unknown)}")

        opt_id = entry["id"]
        if not isinstance(opt_id, str) or not _OPTION_ID_RE.match(opt_id):
            raise ConfigError(
                f"{label_for_err}.id must match [a-z0-9_]+, got {opt_id!r}"
            )
        if opt_id in seen_ids:
            raise ConfigError(f"duplicate option id {opt_id!r}")
        seen_ids.add(opt_id)

        kind = entry["kind"]
        if kind not in _OPTION_KINDS:
            raise ConfigError(
                f"{label_for_err}.kind must be one of {sorted(_OPTION_KINDS)}, got {kind!r}"
            )

        label = entry["label"]
        if not isinstance(label, str):
            raise ConfigError(f"{label_for_err}.label must be a string")

        target = entry["target"]
        if not isinstance(target, str):
            raise ConfigError(f"{label_for_err}.target must be a string")
        _validate_target_syntax(target, label_for_err)

        default = entry["default"]
        min_v = entry.get("min")
        max_v = entry.get("max")

        choices: tuple[OptionChoice, ...] = ()
        if kind == "enum":
            raw_choices = entry.get("choices")
            if not isinstance(raw_choices, list) or not raw_choices:
                raise ConfigError(f"{label_for_err}.choices must be a non-empty list for kind 'enum'")
            parsed: list[OptionChoice] = []
            for j, ch in enumerate(raw_choices):
                if not isinstance(ch, dict):
                    raise ConfigError(f"{label_for_err}.choices[{j}] must be a mapping")
                if "value" not in ch or "label" not in ch:
                    raise ConfigError(
                        f"{label_for_err}.choices[{j}] missing required fields: ['label', 'value']"
                    )
                parsed.append(OptionChoice(value=ch["value"], label=str(ch["label"])))
            choices = tuple(parsed)
            values = {c.value for c in choices}
            if default not in values:
                raise ConfigError(
                    f"{label_for_err}.default {default!r} is not in choices {sorted(values, key=str)}"
                )
        elif kind in ("int", "hex"):
            if not isinstance(default, int) or isinstance(default, bool):
                raise ConfigError(f"{label_for_err}.default must be an integer for kind {kind!r}")
            if min_v is not None and default < min_v:
                raise ConfigError(f"{label_for_err}.default {default} below min {min_v}")
            if max_v is not None and default > max_v:
                raise ConfigError(f"{label_for_err}.default {default} above max {max_v}")
        elif kind == "bool":
            if not isinstance(default, bool):
                raise ConfigError(f"{label_for_err}.default must be a boolean for kind 'bool'")

        out.append(OptionSpec(
            id=opt_id,
            label=label,
            kind=kind,
            target=target,
            default=default,
            choices=choices,
            min=min_v if isinstance(min_v, int) else None,
            max=max_v if isinstance(max_v, int) else None,
            description=entry.get("description"),
        ))
    return tuple(out)


def _validate_target_syntax(path: str, label: str) -> None:
    if not path:
        raise ConfigError(f"{label}.target must not be empty")
    for token in path.split("."):
        if not _TARGET_TOKEN_RE.match(token):
            raise ConfigError(
                f"{label}.target token {token!r} is malformed — expected 'name' or 'name[key]'"
            )


def _apply_options(
    raw: dict,
    options: tuple[OptionSpec, ...],
    values: dict[str, object],
) -> None:
    """Resolve each option's target path and write its value into the raw dict."""
    # Reject values that don't correspond to any declared option — catches typos early.
    declared_ids = {o.id for o in options}
    unknown = set(values.keys()) - declared_ids
    if unknown:
        raise ConfigError(
            f"Rule 12: option values reference unknown ids: {sorted(unknown)}"
        )

    for opt in options:
        value = values.get(opt.id, opt.default)
        if opt.kind == "enum" and value not in {c.value for c in opt.choices}:
            raise ConfigError(
                f"Rule 12: option {opt.id!r} value {value!r} is not a declared choice"
            )
        if opt.kind in ("int", "hex"):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConfigError(
                    f"Rule 12: option {opt.id!r} value {value!r} must be an integer"
                )
            if opt.min is not None and value < opt.min:
                raise ConfigError(f"Rule 12: option {opt.id!r} value {value} below min {opt.min}")
            if opt.max is not None and value > opt.max:
                raise ConfigError(f"Rule 12: option {opt.id!r} value {value} above max {opt.max}")
        if opt.kind == "bool" and not isinstance(value, bool):
            raise ConfigError(
                f"Rule 12: option {opt.id!r} value {value!r} must be a boolean"
            )

        container, key = _resolve_target_path(raw, opt.target, opt.id)
        container[key] = value


def _resolve_target_path(
    raw: dict,
    path: str,
    option_id: str,
) -> tuple[dict, str]:
    """
    Walk ``path`` through ``raw`` and return the (container, final_key)
    pair so the caller can write ``container[final_key] = value``. Auto-
    creates missing intermediate mappings (e.g. a missing ``params:``
    block) but never auto-creates through lists.
    """
    tokens = path.split(".")
    cursor: Any = raw
    for i, token in enumerate(tokens):
        match = _TARGET_TOKEN_RE.match(token)
        if match is None:  # pragma: no cover — pre-validated at parse time
            raise ConfigError(
                f"Rule 12: option {option_id!r} target token {token!r} is malformed"
            )
        key, index_spec = match.group(1), match.group(2)
        is_last = (i == len(tokens) - 1)

        if index_spec is None:
            # Plain mapping descent.
            if not isinstance(cursor, dict):
                raise ConfigError(
                    f"Rule 12: option {option_id!r} target {path!r} cannot be resolved: "
                    f"{key!r} is not a mapping"
                )
            if is_last:
                return cursor, key
            if key not in cursor or cursor[key] is None:
                cursor[key] = {}
            cursor = cursor[key]
            continue

        # Indexed list element: descend into cursor[key] (list), then resolve index.
        if not isinstance(cursor, dict) or key not in cursor:
            raise ConfigError(
                f"Rule 12: option {option_id!r} target {path!r} cannot be resolved: "
                f"no list {key!r} found"
            )
        container_list = cursor[key]
        if not isinstance(container_list, list):
            raise ConfigError(
                f"Rule 12: option {option_id!r} target {path!r} cannot be resolved: "
                f"{key!r} is not a list"
            )

        if index_spec.isdigit():
            idx = int(index_spec)
            if idx < 0 or idx >= len(container_list):
                raise ConfigError(
                    f"Rule 12: option {option_id!r} target {path!r} cannot be resolved: "
                    f"index {idx} out of range for {key!r} (len={len(container_list)})"
                )
            cursor = container_list[idx]
        else:
            found = None
            for entry in container_list:
                if isinstance(entry, dict) and entry.get("name") == index_spec:
                    found = entry
                    break
            if found is None:
                raise ConfigError(
                    f"Rule 12: option {option_id!r} target {path!r} cannot be resolved: "
                    f"no entry named {index_spec!r} in {key!r}"
                )
            cursor = found

        if is_last:
            # A bracketed token can't be the terminal — we can only write
            # into a *field* of a list entry, not replace the entry itself.
            raise ConfigError(
                f"Rule 12: option {option_id!r} target {path!r} cannot be resolved: "
                f"indexed token {token!r} must be followed by a field name"
            )

    raise ConfigError(  # pragma: no cover — unreachable if tokens is non-empty
        f"Rule 12: option {option_id!r} target {path!r} produced no terminal"
    )
