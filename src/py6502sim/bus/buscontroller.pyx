"""
CYTHON CONTROLLER COMPONENT CLASS IMPLEMENTATIONS

Simulator definitions and functions for a component controller
"""
from cpython.ref cimport PyObject, Py_INCREF, Py_DECREF
from py6502sim.bus.component cimport Component
from py6502sim.cpu.mos6502 cimport MOS6502, Registers

class ComponentSizeError(Exception):
    """
    Component's size cannot fit inside address range
    """

class AddressRangeUnavailable(Exception):
    """
    Address range is already occupied by another component
    """

class UnallocatedAddressError(Exception):
    """
    Atempted to access an address not allocated to a component
    """

cdef class BusController(Component):
    """
    Class definition for an 8-bit component controller
    """
    def __init__(self, str controller_name, MOS6502 processor, bint raise_on_unmapped_access=True) -> None:
        # Controllers will always only have 16-bit address space
        super().__init__(0x10000, controller_name)
        self._processor = processor
        self._processor.set_memory_bus(self)
        self._current_data_bus = 0
        self._current_address_bus = 0
        self._current_read_write = True
        self._raise_on_unmapped_access = raise_on_unmapped_access

    def __dealloc__(self) -> None:
        for i in range(0x10000):
            if self._component_address_map[i].component is not NULL:
                Py_DECREF(<Component>self._component_address_map[i].component)
                self._component_address_map[i].component = NULL

    cpdef void add_component(self, Component component, unsigned int address_start) except *:
        """
        Add a component to the controller

        Arguments:
            - component (Component): Component to be added
            - address_start (unsigned int): Address offset where the controller should begin
                mapping addresses to the component
        """
        address_end = component.get_size() + address_start - 1
        if address_end > 0xffff:
            raise ComponentSizeError(
                f'[{self.get_name()}] Unable to fit {component.get_name()} in '
                f'at address 0x{address_start:04X}.'
            )


        # First check if all addresses are available
        for i in range(component.get_size()):
            if self._component_address_map[address_start+i].component is not NULL:
                conflict_name = (
                    <Component>self._component_address_map[address_start+i].component
                ).get_name()
                raise AddressRangeUnavailable(
                    f'[{self.get_name()}] Component {component.get_name()} cannot be added. '
                    f'Address overlap at 0x{address_start+i:04X} with {conflict_name}.'
                )

        # Then map the addresses
        for i in range(component.get_size()):
            self._component_address_map[address_start+i].internal_address = i
            self._component_address_map[address_start+i].component = <PyObject*>component
            Py_INCREF(component)

    cpdef void clock(self):
        self._processor.clock()

    cpdef void send_reset(self):
        self._processor.send_reset()

    cpdef Registers get_registers(self):
        return self._processor.get_registers()

    cpdef void set_registers(self, Registers registers):
        self._processor.set_registers(registers)

    def get_bus_values(self):
        return self._current_address_bus, self._current_data_bus, self._current_read_write

    cpdef unsigned char execute(self, unsigned int address, unsigned char data, bint read_write_bar) except *:
        self.address_check(address) # Assert address within controller's address range
            
        if self._component_address_map[address].component is NULL:
            if self._raise_on_unmapped_access:
                raise UnallocatedAddressError(
                    f'[{self.get_name()}] Address not allocated to a component: 0x{address:04X}'
                )
            else:
                return 0

        cdef Component component = <Component>self._component_address_map[address].component

        self._current_read_write = read_write_bar
        self._current_address_bus = address
        self._current_data_bus = component.execute(
            self._component_address_map[address].internal_address,
            data,
            read_write_bar
        )

        return self._current_data_bus
