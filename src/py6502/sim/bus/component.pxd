"""
CYTHON BASE COMPONENT CLASS DECLARATIONS
"""

cdef class Component:
    cdef readonly unsigned int _size
    cdef readonly str _name
    cdef inline str get_name(self)
    cdef inline unsigned int get_size(self)
    cdef unsigned char read(self, unsigned short address) except *
    cdef unsigned char write(self, unsigned short address, unsigned char data) except *
    cdef void bind(self, object system)
    cdef void on_cycles_elapsed(self, unsigned long n)
