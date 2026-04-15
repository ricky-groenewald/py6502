"""
EmptyAddress: A dummy component for unmapped addresses.

This component implements dummy read and write operations.
If 'raise_on_unmapped' is True, any read or write will raise an UnallocatedAddressError.
Otherwise, the operations simply return 0.
"""

from py6502.sim.bus.component cimport Component
from cython cimport boundscheck, wraparound

class UnallocatedAddressError(Exception):
    """
    Atempted to access an address not allocated to a component
    """

cdef class EmptyAddress(Component):
    def __init__(self, str name, bint raise_on_unmapped) -> None:
        # The size is arbitrary because the internal address passed in is ignored.
        super().__init__(0, name)
        self._raise_on_unmapped = raise_on_unmapped
        self._bus_data_ptr = NULL

    cdef void set_bus_data_ptr(self, unsigned char* ptr):
        self._bus_data_ptr = ptr

    @boundscheck(False)
    @wraparound(False)
    cdef int read(self, unsigned short address) except -1:
        if self._raise_on_unmapped:
            raise UnallocatedAddressError(
                f'Address not allocated to a component: 0x{address:04X}'
            )
        return self._bus_data_ptr[0]

    @boundscheck(False)
    @wraparound(False)
    cdef int write(self, unsigned short address, unsigned char data) except -1:
        if self._raise_on_unmapped:
            raise UnallocatedAddressError(
                f'Address not allocated to a component: 0x{address:04X}'
            )
        return data