"""
EmptyAddress: the sentinel component for unmapped bus addresses.

Real hardware doesn't have "unmapped" memory in the Python sense — it
either floats the bus (open-bus behaviour: whatever was last driven on
the data lines lingers there) or behaves in some platform-specific way.
We model both modes:

- ``raise_on_unmapped=True`` — strict mode. Every access raises
  ``UnallocatedAddressError``. This is what tests and debug builds
  want: no silent reads of garbage data.
- ``raise_on_unmapped=False`` — open-bus mode. Reads return the last
  byte the bus controller saw (via ``set_bus_data_ptr``), writes are
  swallowed. This is the production setting for emulating machines
  that genuinely tolerate unmapped accesses.

The toggle lives on the BusController side and is flipped at runtime
via ``set_unmapped_memory_mode`` — the user sees it in the Settings
window as "Halt on unmapped memory".
"""

from py6502.sim.bus.component cimport Component
from cython cimport boundscheck, wraparound

class UnallocatedAddressError(Exception):
    """
    Attempted to access an address not allocated to a component.
    """

cdef class EmptyAddress(Component):
    def __init__(self, str name, bint raise_on_unmapped) -> None:
        # ``size=0`` because EmptyAddress never owns a region itself —
        # it's only ever installed as the sentinel in slots that haven't
        # been claimed by a real Component.
        super().__init__(0, name)
        self._raise_on_unmapped = raise_on_unmapped
        self._bus_data_ptr = NULL

    cdef void set_bus_data_ptr(self, unsigned char* ptr):
        # The BusController hands us a pointer to its ``_current_bus_data``
        # so open-bus reads can return the last byte that was driven.
        self._bus_data_ptr = ptr

    @boundscheck(False)
    @wraparound(False)
    cdef int read(self, unsigned short address) except -1:
        # Strict mode raises; open-bus mode returns whatever's lingering
        # on the bus (see module docstring).
        if self._raise_on_unmapped:
            raise UnallocatedAddressError(
                f'Address not allocated to a component: 0x{address:04X}'
            )
        return self._bus_data_ptr[0]

    @boundscheck(False)
    @wraparound(False)
    cdef int write(self, unsigned short address, unsigned char data) except -1:
        # Strict mode raises; open-bus mode silently accepts the write
        # (the byte goes nowhere — there's no memory here).
        if self._raise_on_unmapped:
            raise UnallocatedAddressError(
                f'Address not allocated to a component: 0x{address:04X}'
            )
        return data