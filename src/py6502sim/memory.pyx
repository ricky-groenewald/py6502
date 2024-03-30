"""
CYTHON MEMORY COMPONENT CLASS IMPLEMENTATIONS

Definitions and functions for a memory component
"""
from libc.stdlib cimport malloc, free
from libc.string cimport memset
from cython cimport boundscheck, wraparound
from .component cimport Component

class DataSizeError(Exception):
    """
    Input data size does not match up with memory data capacity
    """

class MemoryAllocationError(Exception):
    """
    Memory could not be allocated for data array
    """

cdef class Memory(Component):
    """
    Class definition for a memory component
    """
    def __init__(self, unsigned int size, str memory_name, bint read_only) -> None:
        super().__init__(size, memory_name)
        self._data = <unsigned char *>malloc(self.get_size() * sizeof(unsigned char))
        if self._data is NULL:
            raise MemoryError('Failed to allocate memory for the data array.')
        memset(self._data, 0, self.get_size() * sizeof(unsigned char))

        self._read_only = read_only

    def __dealloc__(self):
        if self._data is not NULL:
            free(self._data)

    # Wraparound disabled since address is strictly positive
    # Bounds checking disabled since _read should only ever be accessed through "execute"
    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char _read(self, unsigned int address):
        return self._data[address]

    # Wraparound disabled since address is strictly positive
    # Bounds checking disabled since _read should only ever be accessed through "execute"
    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char _write(self, unsigned int address, unsigned char data):
        if not self._read_only:
            self._data[address] = data

        return self._data[address]

    def _detail_str_output(self) -> str:
        str_output = 'Data content:'

        for offset in range(0, self.get_size(), 16):
            str_output += f'\n0x{offset:X}: '

            str_output += ' '.join([f'{byte:02X}' for byte in self._data[offset:offset+8]])
            str_output += '    '
            str_output += ' '.join([f'{byte:02X}' for byte in self._data[offset+8:offset+16]])

        return str_output

    def set_data_from_array(self, data: list[int]) -> None:
        """
        Overwrites memory with an identically sized data array.

        Bypasses "read_only" value.

        Arguments:
            - data (list[int])
        """
        if len(data) != self.get_size():
            raise DataSizeError(
                f'[{self.get_name()}] Cannot upload data into memory. '
                f'Expected {self.get_size()} bytes, but received {len(data)} bytes.'
            )

        for i, byte in enumerate(data):
            self._data[i] = <unsigned char>byte

    cpdef unsigned char read_addr(self, unsigned int address):
        """
        Reads a byte from the memory component at the specified address.

        Arguments:
            - address (unsigned int): Address to read from

        Returns:
            - unsigned char: Data read from the memory component
        """
        return self._read(address)