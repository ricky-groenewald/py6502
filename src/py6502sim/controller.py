"""
Simulator definitions and functions for a component controller
"""
from py6502sim import Component

class ComponentSizeError(Exception):
    """
    Component's size cannot fit inside address range
    """

class ComponentExistsError(Exception):
    """
    Component already exists
    """

class AddressRangeUnavailable(Exception):
    """
    Address range is already occupied by another component
    """

class UnallocatedAddressError(Exception):
    """
    Atempted to access an address not allocated to a component
    """

class Controller(Component):
    """
    Class definition for a component controller
    """
    def __init__(self, controller_name: str) -> None:
        super().__init__(0xffff, controller_name)
        self._components: list[(Component, int, int)] = []

    def add_component(self, component: Component, address_start: int):
        """
        Add a component to the controller

        Arguments:
            component (Component): An initialized component of any type
            address_start (int): Address offset where the controller should begin assigning
                address space to the component
        """
        address_end = component.get_max_address() + address_start
        if address_end > 0xffff:
            raise ComponentSizeError(
                f'[{self._name}] Unable to fit {component.get_name()} in '
                f'at address 0x{address_start:04X}.'
            )

        if component in [c[0] for c in self._components]:
            raise ComponentExistsError(
                f'[{self._name}] Component {component.get_name()} already added to controller.'
            )

        for existing_comp in self._components:
            if (
                existing_comp[1] <= address_start <= existing_comp[2] or
                existing_comp[1] <= address_end <= existing_comp[2]
            ):
                raise AddressRangeUnavailable(
                    f'[{self._name}] Component {component.get_name()} cannot be added. '
                    f'Address range will overlap with {existing_comp[0].get_name()}'
                )

        self._components.append((component, address_start, address_end))
        self._components.sort(key=lambda x: x[1])

    def execute(self, address: int, data: int, flags: dict) -> int:
        self._address_and_data_check(address, data)

        for component in self._components:
            if component[1] <= address <= component[2]:
                return component.execute(address - component[1], data, flags)

        raise UnallocatedAddressError(
            f'[{self._name}] Address not allocated to a component: 0x{address:04X}'
        )

    def _detail_str_output(self):
        return 'Component list:\n' + '\n'.join(
            [f'{c[0]} [0x{c[1]:04X} - 0x{c[2]:04X}]' for c in self._components]
        )
