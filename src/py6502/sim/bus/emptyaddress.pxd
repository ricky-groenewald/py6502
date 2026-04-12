from py6502.sim.bus.component cimport Component

cdef class EmptyAddress(Component):
    cdef bint _raise_on_unmapped
    cdef unsigned char* _bus_data_ptr

    cdef unsigned char read(self, unsigned short address) except *
    cdef unsigned char write(self, unsigned short address, unsigned char data) except *
    cdef void set_bus_data_ptr(self, unsigned char* ptr)
