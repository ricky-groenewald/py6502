"""
CYTHON CONTROLLER COMPONENT CLASS DECLARATIONS

Simulator definitions and functions for a component controller
"""
from cpython.ref cimport PyObject
from py6502sim.bus.component cimport Component
from py6502sim.cpu.mos6502 cimport MOS6502, Registers

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
    cdef unsigned char _current_data_bus
    cdef unsigned short _current_address_bus
    cdef bint _current_read_write
    cdef bint _raise_on_unmapped_access

    cpdef void add_component(self, Component component, unsigned int address_start) except *

    cpdef void clock(self)

    cpdef void send_reset(self)

    cpdef Registers get_registers(self)
    cpdef void set_registers(self, Registers registers)
