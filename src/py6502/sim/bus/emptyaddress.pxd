from py6502.sim.bus.component cimport Component

cdef class EmptyAddress(Component):
    cdef bint _raise_on_unmapped

    cdef unsigned char read(self, unsigned short address)
    cdef unsigned char write(self, unsigned short address, unsigned char data)
