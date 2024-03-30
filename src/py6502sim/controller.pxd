"""
CYTHON CONTROLLER COMPONENT CLASS DECLARATIONS

Simulator definitions and functions for a component controller
"""
from cpython.ref cimport PyObject
from .component cimport Component

"""
Struct holding the target component and address for a given mapped address
"""
cdef struct MappedAddress:
    PyObject* component
    unsigned int internal_address

cdef class Controller(Component):
    """
    Class definition for an 8-bit component controller
    """
    cdef MappedAddress[0x10000] _component_address_map

    cpdef add_component(self, Component component, unsigned int address_start) except *