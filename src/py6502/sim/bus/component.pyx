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
    cdef unsigned char read(self, unsigned short address):
        """
        SHOULD NOT BE ACCESSED PUBLICLY

        Read data from an address

        Arguments:
            - address (unsigned short)

        Returns:
            Byte value of the data at the specified address
        """
        raise NotImplementedError("Subclass must implement this method")

    # Abstract class
    cdef unsigned char write(self, unsigned short address, unsigned char data):
        """
        SHOULD NOT BE ACCESSED PUBLICLY

        Write data to an address

        Arguments:
            - address (unsigned short)
            - data (unsigned char)

        Returns:
            Byte value of the data written to the address
        """
        raise NotImplementedError("Subclass must implement this method")
