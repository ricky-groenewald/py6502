"""
Class abstract and error definitions for a component connecting to the 6502 processor
"""

class InvalidData(Exception):
    """
    Data value is invalid
    """

class InvalidAddressRange(Exception):
    """
    Specified address range is not a 16-bit range
    """

class AddressOutOfRange(Exception):
    """
    Address value is out of address range
    """

class Component:
    """
    Class definition a component connecting to the 6502 processor
    """
    def __init__(self, max_address: int, component_name: str) -> None:
        """
        Initializes a component with a fixed accessible address range

        Arguments:
            max_address (int): 16-bit value for last accessible address
        """
        if not 0x0000 <= max_address <= 0xffff:
            raise InvalidAddressRange(
                f'Error initializing {component_name} -- '
                f'Invalid maximum address for component: 0x{max_address:04X}'
            )

        self._max_address = max_address
        self._name = component_name

    def get_name(self) -> str:
        """
        Return component name
        """
        return self._name

    def get_max_address(self) -> int:
        """
        Return component maximum address value
        """
        return self._max_address

    def _address_and_data_check(self, address: int, data: int) -> None:
        if not 0x0000 <= address <= self._max_address:
            raise AddressOutOfRange(
                f'[{self._name}] Invalid address accessed: 0x{address:04X}.'
                f' Max address is: 0x{self._max_address:04X}.'
            )

        if not 0x00 <= data <= 0xff:
            raise InvalidData(f'[{self._name}] Invalid byte value obtained: 0x{data:02X}')


    def execute(self, address: int, data: int, read_write_bar: bool) -> int:
        """
        Execute an instruction given values for the address, data, and various processor flags

        Arguments:
            address (int): 16-bit value of the address bus
            data (int): 8-bit value of the data bus
            read_write_bar (bool): Boolean value for the RWB pin (Read on 1, Write on 0)

        Returns:
            int: Byte value of the data bus after the instruction
        """
        self._address_and_data_check(address, data)

        return self._read(address) if read_write_bar else self._write(address, data)

    def _read(self, _address: int) -> int:
        # Process address read here

        # Base class always returns 0
        return 0

    def _write(self, _address: int, data: int) -> int:
        # Process data write to address here

        # Base class simply echoes data
        return data

    def _detail_str_output(self) -> str:
        return

    def __str__(self) -> str:
        str_output = (
            f'Component name: {self._name}\n'
            f'Component type: {type(self).__name__}\n'
            f'Internal address range: 0x0000 - 0x{self._max_address:04X}\n'
            f'{self._detail_str_output()}'
        )

        return str_output
