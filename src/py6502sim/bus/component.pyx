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

    cdef void address_check(self, unsigned int address) except *:
        """
        Check if an address is within the component's address range

        Arguments:
            - address (unsigned int)
        """
        if address >= self._size:
            raise AddressOutOfRange(
                f'[{self._name}] Invalid address accessed: 0x{address:X}.'
                f' Max address is: 0x{self._size - 1:X}.'
            )

    cpdef unsigned char execute(self, unsigned int address, unsigned char data, bint read_write_bar) except *:
        """
        Execute an instruction given values for the address and data

        Arguments:
            - address (unsigned int)
            - data (unsigned char)
            - read_write_bar (bool): Read on 1, Write on 0

        Returns:
            Byte value of the data bus after the instruction
        """
        self.address_check(address)

        return self._read(address) if read_write_bar else self._write(address, data)

    # Abstract class
    cdef unsigned char _read(self, unsigned int address):
        """
        SHOULD NOT BE ACCESSED PUBLICLY

        Read data from an address

        Arguments:
            - address (unsigned int)

        Returns:
            Byte value of the data at the specified address
        """
        raise NotImplementedError("Subclass must implement this method")

    # Abstract class
    cdef unsigned char _write(self, unsigned int address, unsigned char data):
        """
        SHOULD NOT BE ACCESSED PUBLICLY

        Write data to an address

        Arguments:
            - address (uint)
            - data (char)

        Returns:
            Byte value of the data written to the address
        """
        raise NotImplementedError("Subclass must implement this method")
