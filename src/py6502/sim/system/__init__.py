"""
System orchestration layer for py6502.sim.

Public surface:
    - ``System``                        — the Cython orchestrator
    - ``SystemConfig``                  — frozen dataclass representation of a config
    - ``ConfigError``                   — raised by the loader on validation failures
    - ``from_yaml_file``                — load + validate a YAML config into a ``SystemConfig``
    - ``from_yaml_file_with_options``   — same, with user-selected option values
    - ``OptionSpec`` / ``OptionChoice`` — user-selectable preset options
"""
from .config import (
    BusSpec,
    ComponentSpec,
    ConfigError,
    CpuSpec,
    MemoryRegion,
    OptionChoice,
    OptionSpec,
    SystemConfig,
)
from .loader import from_yaml_file, from_yaml_file_with_options
from .system import System
from .writer import to_yaml_text, write_yaml_file

__all__ = [
    "BusSpec",
    "ComponentSpec",
    "ConfigError",
    "CpuSpec",
    "MemoryRegion",
    "OptionChoice",
    "OptionSpec",
    "System",
    "SystemConfig",
    "from_yaml_file",
    "from_yaml_file_with_options",
    "to_yaml_text",
    "write_yaml_file",
]
