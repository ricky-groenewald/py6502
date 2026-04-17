from py6502.sim.bus.component cimport Component

cdef class EmptyAddress(Component):
    cdef bint _raise_on_unmapped
    cdef unsigned char* _bus_data_ptr

    cdef int read(self, unsigned short address) except -1
    cdef int write(self, unsigned short address, unsigned char data) except -1
    cdef void set_bus_data_ptr(self, unsigned char* ptr)
