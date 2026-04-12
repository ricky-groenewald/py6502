"""
CYTHON SYSTEM ORCHESTRATION CLASS DECLARATIONS
"""
from py6502.sim.bus.component cimport Component
from py6502.sim.cpu.mos6502 cimport MOS6502, Registers


cdef class System:
    cdef MOS6502 _cpu
    cdef unsigned long _cpu_hz
    cdef dict _buses
    cdef Component _display
    cdef list _inputs
    cdef dict _memory_regions

    cpdef void run_cycles(self, unsigned long cycles)
    cpdef void run_for_microseconds(self, unsigned long microseconds)
    cpdef void reset(self)
    cpdef void load_binary(self, str region_name, unsigned int offset, bytes data)
    cpdef Registers get_registers(self)
    cpdef void set_registers(self, Registers registers)
    cpdef object get_framebuffer(self)
    cpdef void register_tick_hook(self, object component)
    cpdef unsigned char peek(self, unsigned short address)
    cpdef unsigned char poke(self, unsigned short address, unsigned char data)

    cdef Component _instantiate_component(self, object spec)
    cdef void _wire_component(self, Component component, unsigned int address, str bus_name)
