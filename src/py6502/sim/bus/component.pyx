"""
CYTHON BASE COMPONENT CLASS IMPLEMENTATIONS

Class abstract and error definitions for a component connecting to the 6502 processor
"""
from cython cimport wraparound

class AddressOutOfRange(Exception):
    """
    Address value is out of address range
    """

cdef class Component:
    """
    Base class definition for addressable components
    """
    def __init__(self, unsigned int size, str component_name):
        """
        Initializes a component with a fixed address range

        Arguments:
            - size (unsigned int): size of the address range in bytes
            - component_name (str): name of the component
        """
        self._size = size
        self._name = component_name

    cdef inline str get_name(self):
        """
        Return component name
        """
        return self._name

    cdef inline unsigned int get_size(self):
        """
        Return component address range size
        """
        return self._size

    # Abstract class
    cdef int read(self, unsigned short address) except -1:
        """
        SHOULD NOT BE ACCESSED PUBLICLY

        Read data from an address

        Arguments:
            - address (unsigned short)

        Returns:
            Byte value (0-255) of the data at the specified address.
            Declared `cdef int ... except -1` so Cython can propagate
            exceptions via a cheap cmp-against-sentinel rather than a
            per-call PyErr_Occurred() — the happy-path return is always
            in [0, 255] and -1 is reserved as the error sentinel.
        """
        raise NotImplementedError("Subclass must implement this method")

    # Abstract class
    cdef int write(self, unsigned short address, unsigned char data) except -1:
        """
        SHOULD NOT BE ACCESSED PUBLICLY

        Write data to an address

        Arguments:
            - address (unsigned short)
            - data (unsigned char)

        Returns:
            The byte value (0-255) that was written — subclasses
            should return `data` on success to preserve the bus-line
            contract. Declared `cdef int ... except -1` so Cython
            can propagate exceptions via a cheap cmp-against-sentinel
            on the hot path (the happy-path return is always in
            [0, 255] and -1 is reserved as the error sentinel).
        """
        raise NotImplementedError("Subclass must implement this method")

    cdef void bind(self, object system):
        """
        Late-binding hook. Called by System.__init__ on every component
        after all components have been instantiated and added to their
        bus. Overrides grab cross-component refs or register tick hooks.
        Default: no-op.
        """
        pass

    cdef void on_cycles_elapsed(self, unsigned long n):
        """
        Batch-end tick hook. Fired once at the end of every
        BusController.run_cycles(N) call for every component that
        subscribed via BusController.register_tick_hook. Default: no-op.

        The iteration is O(num_tick_hooks) per batch, not per cycle —
        this hook is cheap even when many components subscribe.
        """
        pass

    cdef list get_framebuffer(self):
        """Return an RGBA float list for display components. Default: None."""
        return None

    cdef bint send_input(self, unsigned char char_):
        """Accept an input byte (e.g. a key press). Default: False (ignored)."""
        return False

    cdef void clear_input(self):
        """Clear any pending input buffer. Default: no-op."""
        pass
