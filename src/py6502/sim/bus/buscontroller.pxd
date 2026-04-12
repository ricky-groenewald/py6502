"""
CYTHON CONTROLLER COMPONENT CLASS DECLARATIONS

Simulator definitions and functions for a component controller
"""
from cpython.ref cimport PyObject
from py6502.sim.bus.component cimport Component
from py6502.sim.bus.emptyaddress cimport EmptyAddress
from py6502.sim.cpu.mos6502 cimport MOS6502, Registers

"""
Struct holding the target component and address for a given mapped address
"""
cdef struct MappedAddress:
    PyObject* component
    unsigned short internal_address

cdef class BusController(Component):
    """
    Class definition for an 8-bit component controller
    """
    cdef MappedAddress[0x10000] _component_address_map
    cdef MOS6502 _processor
    cdef unsigned short _current_bus_address
    cdef unsigned char _current_bus_data
    cdef bint _current_bus_read_write_bar
    cdef EmptyAddress _empty_address
    cdef list _tick_hooks

    cdef void add_component(self, Component component, unsigned int address_start) except *
    cdef void register_tick_hook(self, object component)

    cdef void clock(self) except *
    cdef void run_cycles(self, unsigned long cycles) except *
    cdef void run_for_microseconds(self, unsigned long microseconds, unsigned long cpu_hz) except *

    cdef void send_reset(self)

    cdef Registers get_registers(self)
    cdef void set_registers(self, Registers registers)

    cdef bint is_mapped(self, unsigned short address)
    cdef void set_unmapped_memory_mode(self, bint crash)

    cdef tuple get_bus_values(self)
