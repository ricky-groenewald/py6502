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
from py6502.sim.system.loader import regions_covering, resolve_source, validate_coverage
from py6502.sim.system.registry import resolve as _resolve_type


cdef class System:
    """
    The Python-facing object that owns a whole machine.

    ``System`` is the *only* surface the frontend is meant to touch. It
    holds the CPU, the bus(es), and every live Component, built once
    from a ``SystemConfig`` and then frozen. The frontend makes one
    coarse call per UI frame (``run_for_microseconds`` / ``run_cycles``)
    and reads back cheap snapshots (``get_framebuffer``,
    ``get_registers``) — everything else happens behind the Cython wall.

    See ``docs/ARCHITECTURE.md`` §3.6 for the runtime model and
    ``docs/SYSTEM_CONFIG.md`` §10 for the build sequence this class
    implements.
    """
    def __init__(self, config, base_dir=None):
        cdef Component component
        cdef BusController main_bus
        cdef Memory mem

        if not isinstance(config, SystemConfig):
            raise TypeError(f"System expects a SystemConfig, got {type(config).__name__}")

        self._cpu_hz = config.cpu.hz
        self._buses = {}
        self._memory_regions = {}
        self._memory_config = config.memory
        self._inputs = []
        self._display = None

        # Resolve the CPU class via the registry, not a hardcoded import:
        # the config's ``cpu.type`` string is the source of truth, which
        # keeps the door open for future cores (65C02 in v0.3, etc.).
        cpu_cls = _resolve_type(config.cpu.type)
        self._cpu = cpu_cls()

        # v0.1 is single-bus. ``buses`` is already a dict so v0.2 can
        # carry a CPU bus + PPU bus without changing this class's shape.
        main_bus = BusController("main", self._cpu, False)
        self._buses["main"] = main_bus

        # --- Memory regions ---------------------------------------------
        # Walk the validated memory layout and wire every region onto
        # its declared bus. ``base_dir`` anchors later ``file:`` URI
        # resolution; default is CWD for programmatic callers.
        resolve_base = Path(base_dir) if base_dir is not None else Path.cwd()
        for region in config.memory:
            mem = Memory(region.size, region.name, region.read_only)
            self._wire_component(mem, region.start, region.bus)
            self._memory_regions[region.name] = mem

        # --- Binary sources ---------------------------------------------
        # Rule 13 (binaries cover a contiguous mapped range with no
        # gaps and no overlap — see docs/SYSTEM_CONFIG.md §8) has
        # already been validated by the loader, so this loop can trust
        # the config and just walk covering regions, slicing bytes
        # into each. Memory.set_data bypasses the read_only guard on
        # purpose: ROM *payloads* are precisely what we're loading.
        for bs in config.binaries:
            data = resolve_source(bs.source, resolve_base)
            cursor = bs.address
            offset = 0
            remaining = len(data)
            for region in regions_covering(config.memory, bs.bus, bs.address, remaining):
                local = cursor - region.start
                take = min(region.size - local, remaining)
                (<Memory>self._memory_regions[region.name]).set_data(
                    list(data[offset:offset + take]), local
                )
                cursor += take
                offset += take
                remaining -= take
                if remaining == 0:
                    break

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

        # Late-binding: every display/input component gets a chance to
        # grab cross-component refs or subscribe to tick hooks now that
        # every other component has been added to the bus. Doing this
        # in a separate pass lets a component's ``bind()`` look up any
        # peer without worrying about initialisation order (see
        # Apple1Display.bind for a typical use — reading cpu_hz and
        # registering the batch-end tick hook).
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
        """
        Run exactly ``cycles`` CPU cycles. The low-level primitive — no
        display sync, so tests and internal callers pay nothing for the
        per-frame render. The frontend does not call this on the hot
        path; it calls ``run_for_microseconds`` (which syncs) or the
        debug-only ``step_cycle`` / ``step_instruction`` (which also
        sync).
        """
        if cycles:
            (<BusController>self._buses["main"]).run_cycles(cycles)

    cpdef void run_for_microseconds(self, unsigned long microseconds) except *:
        """
        Run for the wall-clock elapsed time the frontend observed this
        frame. Converted to cycles against the configured ``cpu_hz`` so
        the effective frequency stays locked regardless of UI refresh
        rate. Triggers the once-per-frame display render at the end, so
        the RGBA buffer the frontend's raw texture is bound to reflects
        the latest sim state before DPG re-uploads to the GPU.
        """
        if microseconds:
            (<BusController>self._buses["main"]).run_for_microseconds(microseconds, self._cpu_hz)
        self.sync_display()

    cpdef unsigned long step_cycle(self) except *:
        """
        Advance one CPU cycle. Used by the debug panel's Cycle button.
        Syncs the display so single-step actions are visible in the
        video window without waiting for the next frame tick.
        """
        (<BusController>self._buses["main"]).run_cycles(1)
        self.sync_display()
        return 1

    cpdef unsigned long step_instruction(self) except *:
        """
        Advance until the next instruction boundary. The CPU core
        latches ``OPCODE`` / ``OPCODE_ADDR`` at the start of each
        instruction, so "the boundary" is "the first cycle where at
        least one of those two registers changes". The 16-cycle cap is
        a safety net: the longest legal 6502 instruction takes 7 cycles
        (RTI + page-cross variants), so anything past 16 means we've
        somehow lost the marker and should bail rather than spin. Syncs
        the display on the way out for the same reason ``step_cycle``
        does.
        """
        cdef BusController bus = <BusController>self._buses["main"]
        cdef Registers start = bus.get_registers()
        cdef unsigned short start_addr = start.OPCODE_ADDR
        cdef unsigned char start_op = start.OPCODE
        cdef unsigned long cycles = 0
        cdef Registers current
        while True:
            bus.run_cycles(1)
            cycles += 1
            current = bus.get_registers()
            if current.OPCODE_ADDR != start_addr or current.OPCODE != start_op:
                break
            if cycles > 16:
                break
        self.sync_display()
        return cycles

    cpdef void reset(self):
        """Reset the CPU. Peripherals see no reset signal of their own."""
        (<BusController>self._buses["main"]).send_reset()

    cpdef void load_binary_at(self, unsigned int address, bytes data):
        """
        Runtime counterpart to config-time binary loading. Writes ``data``
        onto the main bus starting at ``address``, walking across
        contiguous memory regions exactly like ``__init__`` does.

        ``validate_coverage`` runs the same Rule 13-shape checks the
        loader applies to config-time binaries (non-empty, address lies
        inside a region, regions are contiguous, payload doesn't run off
        the end) and returns the covering regions for the write loop.

        Like config-time loads, this writes through ``Memory.set_data``
        which bypasses the ``read_only`` flag — loading a ROM image at
        runtime is intentional, not a bug.
        """
        cdef unsigned int cursor, local, take, offset, remaining
        if address > 0xFFFF:
            raise ConfigError(
                f"load_binary_at: address 0x{address:X} is outside the 16-bit bus"
            )
        covering = validate_coverage(
            self._memory_config,
            "main",
            address,
            len(data),
            label="load_binary_at:",
        )
        cursor = address
        offset = 0
        remaining = len(data)
        for region in covering:
            local = cursor - region.start
            take = min(region.size - local, remaining)
            (<Memory>self._memory_regions[region.name]).set_data(
                list(data[offset:offset + take]), local
            )
            cursor += take
            offset += take
            remaining -= take
            if remaining == 0:
                break

    cpdef Registers get_registers(self):
        """Cheap snapshot of the CPU register file. Safe per frame."""
        return (<BusController>self._buses["main"]).get_registers()

    cpdef void set_registers(self, Registers registers):
        (<BusController>self._buses["main"]).set_registers(registers)

    cpdef object get_framebuffer(self):
        """
        Return the display's RGBA buffer (or None if there's no display).
        Pure reference getter: the buffer is owned by the display
        peripheral and stays pinned for the life of the System, so the
        frontend can safely bind a DearPyGui raw texture to it once
        and never re-read this method on the hot path. The render into
        that buffer happens in ``sync_display`` (invoked at the end of
        every coarse frontend call).
        """
        if self._display is None:
            return None
        return (<Component>self._display).get_framebuffer()

    cpdef void sync_display(self):
        """
        Tell the display peripheral to refresh its RGBA buffer. Invoked
        automatically at the end of ``run_for_microseconds``,
        ``step_cycle``, and ``step_instruction`` so the frontend never
        has to call it. Exposed publicly so tests and one-off frontend
        paths (e.g. the initial-paint on system load) can force a
        render without advancing any cycles.
        """
        if self._display is not None:
            (<Component>self._display).render_framebuffer()

    cpdef void register_tick_hook(self, object component):
        """
        Subscribe a component to the batch-end tick hook. Called from
        a peripheral's ``bind()`` to receive ``on_cycles_elapsed(n)``
        once at the end of every ``run_cycles`` batch.
        """
        (<BusController>self._buses["main"]).register_tick_hook(component)

    cpdef unsigned char peek(self, unsigned short address):
        """Debug read. Goes through the bus but is not cycle-accurate."""
        return (<BusController>self._buses["main"]).read(address)

    cpdef unsigned char poke(self, unsigned short address, unsigned char data):
        """Debug write. Same caveat as ``peek``."""
        return (<BusController>self._buses["main"]).write(address, data)

    cpdef bint is_mapped(self, unsigned short address):
        """True iff ``address`` is owned by a real Component (not the EmptyAddress sentinel)."""
        return (<BusController>self._buses["main"]).is_mapped(address)

    cpdef void set_invalid_opcode_mode(self, unsigned char mode):
        # 0 = treat invalid opcodes as NOPs; 1 = raise InvalidOPCode.
        # 2 = illegal opcode simulation mode
        # Toggled from the Settings window.
        self._cpu.set_invalid_opcode_mode(mode)

    cpdef void set_unmapped_memory_mode(self, bint crash):
        # crash=True: unmapped accesses raise UnallocatedAddressError.
        # crash=False: open-bus behaviour (last data byte lingers).
        (<BusController>self._buses["main"]).set_unmapped_memory_mode(crash)

    cpdef bint send_key(self, unsigned char char_):
        """
        Push one keystroke into the first input peripheral. Returns
        False if its buffer is full so the frontend can hold the key
        and try again next frame.
        """
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
        # Resolve the component's class via the registry (same string
        # → class mapping the loader uses) and call it with the spec's
        # ``params`` dict. A bad ``type`` field yields KeyError from the
        # registry; bad params yield TypeError from the constructor —
        # both surface as ConfigError so the caller has one thing to catch.
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
        # Single point of truth for bus wiring. Today this is a direct
        # add_component call; when non-contiguous address ranges arrive
        # (see ComponentSpec docstring in config.py for the NES PPU
        # mirror example), the multi-range fan-out lives here.
        if bus_name not in self._buses:
            raise ConfigError(f"Component references unknown bus {bus_name!r}")
        (<BusController>self._buses[bus_name]).add_component(component, address)
