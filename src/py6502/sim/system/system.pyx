"""
CYTHON SYSTEM ORCHESTRATION CLASS IMPLEMENTATIONS

Thin Cython wrapper over a single BusController + CPU + component set,
built from a declarative ``SystemConfig`` loaded via the YAML
loader. See docs/ARCHITECTURE.md and docs/SYSTEM_CONFIG.md for the
contract.
"""
from pathlib import Path

from py6502.sim.bus.buscontroller cimport BusController
from py6502.sim.bus.component cimport Component
from py6502.sim.bus.memory cimport Memory
from py6502.sim.cpu.mos6502 cimport MOS6502, Registers

from py6502.sim.system.config import ComponentSpec, ConfigError, MemoryRegion, SystemConfig
from py6502.sim.system.loader import from_yaml_file as _loader_from_yaml_file
from py6502.sim.system.loader import resolve_source
from py6502.sim.system.registry import resolve as _resolve_type


cdef class System:
    def __init__(self, config, base_dir=None):
        cdef Component component
        cdef BusController main_bus
        cdef Memory mem

        if not isinstance(config, SystemConfig):
            raise TypeError(f"System expects a SystemConfig, got {type(config).__name__}")

        self._cpu_hz = config.cpu.hz
        self._buses = {}
        self._memory_regions = {}
        self._inputs = []
        self._display = None

        # Resolve the CPU class via the registry, not a hardcoded import.
        cpu_cls = _resolve_type(config.cpu.type)
        self._cpu = cpu_cls()

        main_bus = BusController("main", self._cpu, False)
        self._buses["main"] = main_bus

        # --- Memory regions ---------------------------------------------
        resolve_base = Path(base_dir) if base_dir is not None else Path.cwd()
        for region in config.memory:
            mem = Memory(region.size, region.name, region.read_only)
            if region.source is not None:
                data = resolve_source(region.source, resolve_base)
                mem.set_data(list(data), region.load_offset)
            self._wire_component(mem, region.start, region.bus)
            self._memory_regions[region.name] = mem

        # --- Display ----------------------------------------------------
        if config.display is not None:
            component = self._instantiate_component(config.display)
            self._wire_component(component, config.display.address, config.display.bus)
            self._display = component

        # --- Inputs -----------------------------------------------------
        for spec in config.inputs:
            component = self._instantiate_component(spec)
            self._wire_component(component, spec.address, spec.bus)
            self._inputs.append(component)

        # --- Audio ------------------------------------------------------
        if config.audio is not None:
            component = self._instantiate_component(config.audio)
            self._wire_component(component, config.audio.address, config.audio.bus)

        # --- Other ------------------------------------------------------
        for spec in config.other:
            component = self._instantiate_component(spec)
            self._wire_component(component, spec.address, spec.bus)

        # Late-binding: every component gets a chance to grab cross-
        # component refs or subscribe to tick hooks now that every other
        # component has been added to the bus.
        if self._display is not None:
            (<Component>self._display).bind(self)
        for input_component in self._inputs:
            (<Component>input_component).bind(self)

        main_bus.send_reset()

    @classmethod
    def from_yaml_file(cls, path):
        """Load and validate a YAML config, then build a System from it."""
        path = Path(path)
        config = _loader_from_yaml_file(path)
        return cls(config, base_dir=path.parent)

    @property
    def cpu_hz(self):
        return self._cpu_hz

    cpdef void run_cycles(self, unsigned long cycles) except *:
        if cycles:
            (<BusController>self._buses["main"]).run_cycles(cycles)

    cpdef void run_for_microseconds(self, unsigned long microseconds) except *:
        if microseconds:
            (<BusController>self._buses["main"]).run_for_microseconds(microseconds, self._cpu_hz)

    cpdef void reset(self):
        (<BusController>self._buses["main"]).send_reset()

    cpdef void load_binary(self, str region_name, unsigned int offset, bytes data):
        if region_name not in self._memory_regions:
            raise KeyError(f"Unknown memory region: {region_name}")
        (<Memory>self._memory_regions[region_name]).set_data(list(data), offset)

    cpdef Registers get_registers(self):
        return (<BusController>self._buses["main"]).get_registers()

    cpdef void set_registers(self, Registers registers):
        (<BusController>self._buses["main"]).set_registers(registers)

    cpdef object get_framebuffer(self):
        if self._display is None:
            return None
        return (<Component>self._display).get_framebuffer()

    cpdef void register_tick_hook(self, object component):
        (<BusController>self._buses["main"]).register_tick_hook(component)

    cpdef unsigned char peek(self, unsigned short address):
        return (<BusController>self._buses["main"]).read(address)

    cpdef unsigned char poke(self, unsigned short address, unsigned char data):
        return (<BusController>self._buses["main"]).write(address, data)

    cpdef bint is_mapped(self, unsigned short address):
        return (<BusController>self._buses["main"]).is_mapped(address)

    cpdef void set_invalid_opcode_mode(self, unsigned char mode):
        self._cpu.set_invalid_opcode_mode(mode)

    cpdef void set_unmapped_memory_mode(self, bint crash):
        (<BusController>self._buses["main"]).set_unmapped_memory_mode(crash)

    cpdef bint send_key(self, unsigned char char_):
        if not self._inputs:
            return False
        return (<Component>self._inputs[0]).send_input(char_)

    cpdef void clear_input_buffer(self):
        if self._inputs:
            (<Component>self._inputs[0]).clear_input()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    cdef Component _instantiate_component(self, object spec):
        cls = _resolve_type(spec.type)
        try:
            instance = cls(**spec.params)
        except TypeError as exc:
            raise ConfigError(
                f"Failed to instantiate {spec.type!r}: {exc}"
            ) from exc
        if not isinstance(instance, Component):
            raise ConfigError(
                f"Registered type {spec.type!r} did not produce a Component subclass"
            )
        return <Component>instance

    cdef void _wire_component(self, Component component, unsigned int address, str bus_name):
        # Single-point-of-truth for bus wiring. Today this is a direct
        # add_component call; when non-contiguous address ranges are
        # added (see ComponentSpec docstring), the extension lives
        # here.
        if bus_name not in self._buses:
            raise ConfigError(f"Component references unknown bus {bus_name!r}")
        (<BusController>self._buses[bus_name]).add_component(component, address)
