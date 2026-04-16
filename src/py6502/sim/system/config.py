"""
Frozen dataclass representation of a py6502 system config.

See docs/SYSTEM_CONFIG.md for the YAML contract, validation rules, and
schema-version policy. This module is the internal form a
`SystemConfig` takes after parsing and validating a YAML file.

All dataclasses are frozen so they can be safely shared, hashed, and
used as cache keys. List fields are represented as tuples for the same
reason.
"""
from dataclasses import dataclass, field
from typing import Optional


class ConfigError(Exception):
    """Raised by the loader when a YAML config fails validation."""


@dataclass(frozen=True)
class CpuSpec:
    type: str
    hz: int


@dataclass(frozen=True)
class BusSpec:
    address_width: int = 16


@dataclass(frozen=True)
class MemoryRegion:
    name: str
    start: int
    size: int
    read_only: bool = False
    bus: str = "main"


@dataclass(frozen=True)
class BinarySource:
    source: str
    address: int
    bus: str = "main"


@dataclass(frozen=True)
class ComponentSpec:
    """
    Spec for one addressable component on a bus.

    v0.1 only supports a single contiguous address range starting at
    ``address`` and spanning ``Component.get_size()`` bytes.
    Non-contiguous layouts (e.g. NES MMIO split across $2000 and
    $4000) are expected to extend this dataclass with an optional
    ``address_ranges: tuple[tuple[int, int], ...]`` field. The bus-
    wiring helper in ``System.__init__`` is factored so that change
    will be additive.
    """
    type: str
    address: int
    bus: str = "main"
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OptionChoice:
    value: object
    label: str


@dataclass(frozen=True)
class OptionSpec:
    """
    A user-selectable preset option.

    ``target`` is a dotted/bracketed path into the raw YAML dict that the
    loader writes the option value to *before* schema validation runs —
    see docs/SYSTEM_CONFIG.md §Options. Supported shapes:

        cpu.<field>
        memory[<name>].<field>
        display.<field>           display.params.<key>
        inputs[<idx>].<field>     inputs[<idx>].params.<key>
        audio.<field>             audio.params.<key>
        other[<idx>].<field>      other[<idx>].params.<key>
    """
    id: str
    label: str
    kind: str
    target: str
    default: object
    choices: tuple[OptionChoice, ...] = ()
    min: Optional[int] = None
    max: Optional[int] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class SystemConfig:
    version: int
    id: str
    name: str
    description: str
    cpu: CpuSpec
    memory: tuple[MemoryRegion, ...]
    buses: dict[str, BusSpec] = field(default_factory=lambda: {"main": BusSpec()})
    display: Optional[ComponentSpec] = None
    inputs: tuple[ComponentSpec, ...] = ()
    audio: Optional[ComponentSpec] = None
    other: tuple[ComponentSpec, ...] = ()
    binaries: tuple[BinarySource, ...] = ()
    author: Optional[str] = None
    tags: tuple[str, ...] = ()
    options: tuple[OptionSpec, ...] = ()
