from py6502.sim.bus.component import Component
from py6502.sim.cpu.mos6502 import MOS6502

from dataclasses import dataclass, field
from typing import Optional, Sequence, Dict

@dataclass
class MemoryRegion:
    '''
    Data class for memory regions
    '''
    name: str
    size: int
    start_address: int
    read_only: bool = False
    initial_data: Optional[Sequence[int]] = None
    initial_data_offset: int = 0


@dataclass
class ComponentSpec:
    '''
    Data class for components that are not peripherals or memory regions
    '''
    name: str
    component_type: type[Component]
    address_map: Dict[int, int] # Map of external address to internal address
    size: int
    params: dict = field(default_factory=dict)


@dataclass
class CpuSpec:
    '''
    Data class for CPUs
    '''
    cpu_type: type[MOS6502]
    cpu_hz: int


@dataclass
class SystemConfig:
    '''
    Data class for system configurations
    '''
    id: str
    name: str
    description: str
    cpu: CpuSpec
    memory_regions: list[MemoryRegion]
    display_device: ComponentSpec
    input_devices: list[ComponentSpec]
    audio_device: ComponentSpec
    other_devices: list[ComponentSpec]
