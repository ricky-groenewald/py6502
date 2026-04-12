"""
CYTHON MEMORY COMPONENT CLASS DECLARATIONS
"""
from py6502.sim.bus.component cimport Component

cdef class Memory(Component):
    cdef unsigned char* _data
    cdef bint _read_only

    cdef void set_data(self, list data, int start_address) except *
    cdef list get_data(self, int start_address, int size)
