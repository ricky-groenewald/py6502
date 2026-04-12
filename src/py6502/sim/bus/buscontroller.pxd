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

    cpdef void add_component(self, Component component, unsigned int address_start) except *
    cpdef void register_tick_hook(self, object component)

    cpdef void testme(self)
    cpdef bint check_success(self)

    cpdef void clock(self) except *
    cpdef void run_cycles(self, unsigned long cycles) except *
    cpdef void run_for_microseconds(self, unsigned long microseconds, unsigned long cpu_hz) except *

    cpdef void send_reset(self)

    cpdef Registers get_registers(self)
    cpdef void set_registers(self, Registers registers)

    cpdef bint is_mapped(self, unsigned short address)
    cpdef void set_unmapped_memory_mode(self, bint crash)
