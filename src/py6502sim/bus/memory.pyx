"""
CYTHON MEMORY COMPONENT CLASS IMPLEMENTATIONS

Definitions and functions for a memory component
"""
from libc.stdlib cimport malloc, free
from libc.string cimport memset
from cython cimport boundscheck, wraparound
from py6502sim.bus.component cimport Component

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
            raise MemoryError(f'[{self.get_name()}] Failed to allocate memory for the data array.')
        memset(self._data, 0, self.get_size() * sizeof(unsigned char))

        self._read_only = read_only

    def __dealloc__(self) -> None:
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

    def set_data(self, data: list[int], start_address: int=0x0000) -> None:
        """
        Writes data to memory starting at the specified address.

        Args:
            data: List of bytes to write to memory
            start_address: Starting memory address (default: 0x0000)

        Raises:
            DataSizeError: If data would exceed available memory space
        
        Note:
            This method bypasses read-only protection
        """
        if len(data) + start_address > self.get_size():
            raise DataSizeError(
                f'[{self.get_name()}] Set data failed: {len(data)} bytes at offset '
                f'0x{start_address:04X} exceeds available memory size of {self.get_size()} bytes'
            )

        for i, byte in enumerate(data):
            self._data[start_address + i] = <unsigned char>byte

    def get_data(self, start_address: int, size: int) -> list[int]:
        """
        Reads a block of data from memory.

        Args:
            start_address: Starting memory address to read from
            size: Number of bytes to read

        Returns:
            List of bytes read from memory

        Raises:
            DataSizeError: If requested range would exceed available memory space
        """
        if start_address + size > self.get_size():
            raise DataSizeError(
                f'[{self.get_name()}] Get data failed: {size} bytes at offset '
                f'0x{start_address:04X} exceeds available memory size of {self.get_size()} bytes'
            )

        return [x for x in self._data[start_address:start_address + size]]
