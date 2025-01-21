"""
CYTHON MEMORY COMPONENT CLASS DECLARATIONS
"""
from py6502sim.bus.component cimport Component

cdef class Memory(Component):
    cdef unsigned char* _data
    cdef bint _read_only
