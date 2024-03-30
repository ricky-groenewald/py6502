"""
CYTHON BASE COMPONENT CLASS DECLARATIONS
"""

cdef class Component:
    cdef readonly unsigned int _size
    cdef readonly str _name
    cpdef str get_name(self)
    cpdef unsigned int get_size(self)
    cpdef unsigned char execute(self, unsigned int address, unsigned char data, bint read_write_bar) except *
    cdef unsigned char _read(self, unsigned int address)
    cdef unsigned char _write(self, unsigned int address, unsigned char data)
