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
    source: Optional[str] = None
    load_offset: int = 0


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
    author: Optional[str] = None
    tags: tuple[str, ...] = ()
