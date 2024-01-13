"""
Simulator definitions and functions for a memory component
"""
from py6502sim import Component

class WritingToReadOnly(Exception):
    """
    Writing to a memory component set to read-only
    """

class Memory(Component):
    """
    Class definition for a memory component
    """
    def __init__(self, max_address: int, memory_name: str, read_only: bool=False) -> None:
        super().__init__(max_address, memory_name)
        self._data = [0] * (self._max_address + 1) # Size starts count at 1, not 0
        self._read_only = read_only

    def _read(self, address: int) -> int:
        return self._data[address]

    def _write(self, address: int, data: int):
        if not self._read_only:
            self._data[address] = data
            return self._data[address]
        raise WritingToReadOnly(f'[{self._name}] Attempting to write to a read-only component.')

    def _detail_str_output(self):
        str_output = 'Data content:'

        for offset in range(0, self._max_address + 1, 16):
            str_output += f'\n0x{offset:04X}: '

            str_output += ' '.join([f'{byte:02x}' for byte in self._data[offset:offset+8]])
            str_output += '    '
            str_output += ' '.join([f'{byte:02x}' for byte in self._data[offset+8:offset+16]])

        return str_output
