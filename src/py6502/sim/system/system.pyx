"""
CYTHON SYSTEM ORCHESTRATION CLASS IMPLEMENTATIONS

Simulator implementations and functions for a complete system orchestrator
"""
from py6502.sim.cpu.mos6502 cimport Registers
from py6502.sim.bus.buscontroller cimport BusController
from py6502.sim.bus.memory cimport Memory

cdef class System:
    def __init__(self, config):
        self._config = config
        self._cpu = config.cpu.cpu_type()
        self._cpu_hz = config.cpu.cpu_hz
        self._bus = BusController("Bus Controller", self._cpu, True)
        self._mem_regions = {}
        self._peripherals = {}

        # Map memory
        for region in config.memory_regions:
            mem = Memory(region.size, region.name, region.read_only)
            if region.initial_data is not None:
                mem.set_data(list(region.initial_data), region.initial_offset)
            self._bus.add_component(mem, region.start_address)
            self._mem_regions[region.name] = mem

        # Map peripherals
        for spec in config.peripherals:
            periph = spec.peripheral_type(self._bus, **spec.params)
            self._bus.add_component(periph, spec.start_address)
            self._peripherals[spec.name] = periph

        self._bus.send_reset()

    cpdef void run_cycles(self, unsigned long cpu_cycles):
        if cpu_cycles > 0:
            self._bus.run_cycles(cpu_cycles)

    cpdef void run_for_microseconds(self, unsigned long microseconds):
        if microseconds > 0:
            self._bus.run_for_microseconds(microseconds, self._cpu_hz)

    cpdef void reset(self):
        self._bus.send_reset()

    cpdef void load_binary(self, str dest_memory, list data, int start_address):
        if dest_memory not in self._mem_regions:
            raise KeyError(f"Unknown memory region: {dest_memory}")
        (<Memory>self._mem_regions[dest_memory]).set_data(list(data), start_address)

    cpdef Registers get_registers(self):
        return self._bus.get_registers()

    # TODO: Add more generic way to get framebuffer
    def get_framebuffer(self):
        periph = self._peripherals.get("Apple1")
        if periph is None:
            return None
        return periph.get_screen_buffer()

    def audio_buffer_depth(self):
        return 0

    def audio_buffer_capacity(self):
        return 0


