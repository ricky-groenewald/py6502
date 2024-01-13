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

        self.max_address = max_address
        self.name = component_name

    def _address_and_data_check(self, address: int, data: int):
        if not 0x0000 <= address <= self.max_address:
            raise AddressOutOfRange(
                f'[{self.name}] Invalid address accessed: 0x{address:04X}.'
                f' Max address is: 0x{self.max_address:04X}.'
            )

        if not 0x00 <= data <= 0xff:
            raise InvalidData(f'[{self.name}] Invalid byte value obtained: 0x{data:02X}')


    def execute(self, address: int, data: int, flags: dict) -> int:
        """
        Execute an instruction given values for the address, data, and various processor flags

        Arguments:
            address (int): 16-bit value of the address bus
            data (int): 8-bit value of the data bus
            flags (dict{key: bool}): A dictionary with all the set processor flags

        Returns:
            int: Byte value of the data bus after the instruction
        """
        self._address_and_data_check(address, data)

        return self._read(address) if flags['RWB'] else self._write(address, data)

    def _read(self, address: int) -> int:
        # Process address read here

        # Base class always returns 0
        return 0

    def _write(self, address: int, data: int):
        # Process data write to address here

        # Base class simply echoes data
        return data

    def _detail_str_output(self):
        return

    def __str__(self):
        str_output = (
            f'Component name: {self.name}\n'
            f'Component type: {type(self).__name__}'
            f'Internal address range: 0x0000 - 0x{self.max_address:04X}\n'
            f'{self._detail_str_output()}'
        )

        return str_output
