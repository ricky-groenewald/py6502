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
    cdef tuple _memory_config

    cpdef void run_cycles(self, unsigned long cycles) except *
    cpdef void run_for_microseconds(self, unsigned long microseconds) except *
    cpdef unsigned long step_cycle(self) except *
    cpdef unsigned long step_instruction(self) except *
    cpdef void reset(self)
    cpdef void load_binary_at(self, unsigned int address, bytes data)
    cpdef Registers get_registers(self)
    cpdef void set_registers(self, Registers registers)
    cpdef object get_framebuffer(self)
    cpdef void register_tick_hook(self, object component)
    cpdef unsigned char peek(self, unsigned short address)
    cpdef unsigned char poke(self, unsigned short address, unsigned char data)
    cpdef bint is_mapped(self, unsigned short address)
    cpdef void set_invalid_opcode_mode(self, unsigned char mode)
    cpdef void set_unmapped_memory_mode(self, bint crash)
    cpdef bint send_key(self, unsigned char char_)
    cpdef void clear_input_buffer(self)

    cdef Component _instantiate_component(self, object spec)
    cdef void _wire_component(self, Component component, unsigned int address, str bus_name)
