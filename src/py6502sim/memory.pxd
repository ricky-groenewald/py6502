"""
CYTHON MEMORY COMPONENT CLASS DECLARATIONS
"""
from .component cimport Component

cdef class Memory(Component):
    cdef unsigned char* _data
    cdef bint _read_only
