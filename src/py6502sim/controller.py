"""
Simulator definitions and functions for a component controller
"""
from py6502sim.component import Component, InvalidData

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
        self._components: list[tuple[Component, int, int]] = []
        self._component_address_map: list[tuple[Component, int]] = [None] * 0x10000

    def add_component(self, component: Component, address_start: int) -> None:
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

        for i in range(component.get_max_address() + 1):
            self._component_address_map[address_start+i] = (component, i)

    def execute(self, address: int, data: int, read_write_bar: bool) -> int:

        # SPEED UP
        # Only do data checking since address checking is implicitly done through the address map
        # Also faster to reimplement the check here.
        if not 0x00 <= data <= 0xff:
            raise InvalidData(f'[{self._name}] Invalid byte value obtained: 0x{data:02X}')

        try:
            component, comp_addr = self._component_address_map[address]
            return (
                component.read(comp_addr) if read_write_bar
                else component.write(comp_addr, data)
            )
        except TypeError as exc:
            raise UnallocatedAddressError(
                f'[{self._name}] Address not allocated to a component: 0x{address:04X}'
            ) from exc

    def _detail_str_output(self) -> str:
        return 'Component list:\n' + '\n'.join(
            [f'{c[0].get_name()} [0x{c[1]:04X} - 0x{c[2]:04X}]' for c in self._components]
        )
