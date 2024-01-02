"""
Simulator definitions and functions for a memory component
"""
from py6502sim import Component

class InvalidMemorySizeError(Exception):
    """
    Specified memory size is invalid
    """

class Memory(Component):
    """
    Class definition for a memory component
    """
    def __init__(self, size: int) -> None:
        if not 0x0000 <= size <= 0xffff:
            raise InvalidMemorySizeError(f'Invalid size for the memory component: {size} bytes')

        super().__init__()
        self._data = [0] * size
