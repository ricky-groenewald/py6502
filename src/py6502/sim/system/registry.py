"""
Component type-name → class registry.

YAML configs reference components by string ("Apple1Display"); this
module is the only place that maps those strings to the actual Cython
classes. Registering a type here is the one step required to make a
new component reachable from IaC configs.

See docs/SYSTEM_CONFIG.md §5 for rationale (security, clear errors,
discoverability, decoupling).
"""
from py6502.sim.bus import Memory
from py6502.sim.cpu.mos6502 import MOS6502
from py6502.sim.peripherals import Apple1Display, Apple1Keyboard


COMPONENT_REGISTRY: dict[str, type] = {
    # CPUs
    "MOS6502": MOS6502,
    # Built-in memory primitive
    "Memory": Memory,
    # Apple I
    "Apple1Display": Apple1Display,
    "Apple1Keyboard": Apple1Keyboard,
}


def resolve(name: str) -> type:
    if name not in COMPONENT_REGISTRY:
        available = ", ".join(sorted(COMPONENT_REGISTRY))
        raise ValueError(
            f"Unknown component type {name!r}. Available: {available}"
        )
    return COMPONENT_REGISTRY[name]
