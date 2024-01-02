"""
Class abstract and error definitions for a component connecting to the 6502 processor
"""

class InvalidAddressError(Exception):
    """
    Address value is invalid
    """

class AddressOutOfRangeError(Exception):
    """
    Address value is out of data range
    """

class InvalidDataError(Exception):
    """
    Data value is invalid
    """

class Component:
    """
    Class definition a component connecting to the 6502 processor
    """
    def __init__(self) -> None:
        self._data: list[int] = []

    def execute(self, address: int, data: int, flags: dict) -> int:
        """
        Execute an instruction given values for the address, data, and various processor flags

        Arguments:
            address (int): 16-bit value of the address bus
            data (int): Byte value of the data bus
            flags (dict{key: bool}): A dictionary with all the set processor flags

        Returns:
            int: Byte value of the data bus after the instruction
        """
        if not 0x0000 <= address <= 0xffff:
            raise InvalidAddressError(f'Invalid address accessed: {address:04x}')

        if not 0x00 <= data <= 0xff:
            raise InvalidDataError(f'Invalid byte value obtained: {data:02x}')

        return self._read(address) if flags['RW'] else self._write(address, data)

    def _read(self, address: int) -> int:
        if address > len(self._data):
            raise AddressOutOfRangeError(f'Address out of data range: {address:04x}')

        return self._data[address]

    def _write(self, address: int, data: int):
        if address > len(self._data):
            raise AddressOutOfRangeError(f'Address out of data range: {address:04x}')

        self._data[address] = data
        return data
