"""
System orchestration layer for py6502.sim.

Public surface:
    - ``System``            — the Cython orchestrator
    - ``SystemConfig``      — frozen dataclass representation of a config
    - ``ConfigError``       — raised by the loader on validation failures
    - ``from_yaml_file``    — load + validate a YAML config into a
      ``SystemConfig``
"""
from .config import (
    BusSpec,
    ComponentSpec,
    ConfigError,
    CpuSpec,
    MemoryRegion,
    SystemConfig,
)
from .loader import from_yaml_file
from .system import System

__all__ = [
    "BusSpec",
    "ComponentSpec",
    "ConfigError",
    "CpuSpec",
    "MemoryRegion",
    "System",
    "SystemConfig",
    "from_yaml_file",
]
