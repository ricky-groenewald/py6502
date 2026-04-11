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

    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char read(self, unsigned short address):
        if self._raise_on_unmapped:
            raise UnallocatedAddressError(
                f'Address not allocated to a component: 0x{address:04X}'
            )
        else:
            return 0

    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char write(self, unsigned short address, unsigned char data):
        if self._raise_on_unmapped:
            raise UnallocatedAddressError(
                f'Address not allocated to a component: 0x{address:04X}'
            )
        else:
            return 0 