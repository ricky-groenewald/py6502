"""
CYTHON CONTROLLER COMPONENT CLASS IMPLEMENTATIONS

Simulator definitions and functions for a component controller
"""
from cpython.ref cimport PyObject, Py_INCREF, Py_DECREF
from cython cimport boundscheck, wraparound
from py6502.sim.bus.component cimport Component
from py6502.sim.bus.emptyaddress cimport EmptyAddress
from py6502.sim.cpu.mos6502 cimport MOS6502, Registers

class ComponentSizeError(Exception):
    """
    Component's size cannot fit inside address range
    """

class AddressRangeUnavailable(Exception):
    """
    Address range is already occupied by another component
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
        self._current_bus_address = 0
        self._current_bus_data = 0
        self._current_bus_read_write_bar = 1
        self._tick_hooks = []
        self._empty_address = EmptyAddress(
            'EmptyAddress',
            raise_on_unmapped_access
        )

        for i in range(0x10000):
            self._component_address_map[i].component = <PyObject*>self._empty_address
            self._component_address_map[i].internal_address = i
            Py_INCREF(self._empty_address)

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
            conflict_name = (
                <Component>self._component_address_map[address_start+i].component
            ).get_name()
            if conflict_name is not self._empty_address.get_name():
                raise AddressRangeUnavailable(
                    f'[{self.get_name()}] Component {component.get_name()} cannot be added. '
                    f'Address overlap at 0x{address_start+i:04X} with {conflict_name}.'
                )

        # Then map the addresses
        for i in range(component.get_size()):
            self._component_address_map[address_start+i].internal_address = i
            self._component_address_map[address_start+i].component = <PyObject*>component
            Py_INCREF(component)
            Py_DECREF(self._empty_address) # NEED TO decrement ref count to empty address

    cpdef void register_tick_hook(self, object component):
        """
        Subscribe a component to the batch-end tick hook. After every
        run_cycles(N) call, the component's on_cycles_elapsed(N) cdef
        method is invoked exactly once — not once per cycle.
        """
        self._tick_hooks.append(component)

    cpdef void testme(self):
        for _ in range(96_247_419):
            self._processor.clock()

    cpdef bint check_success(self):
        return self.read(0x0200) == 0xF0

    cpdef void clock(self):
        self._processor.clock()

    cpdef void run_cycles(self, unsigned long cycles):
        cdef unsigned long i
        cdef Py_ssize_t hook_idx
        cdef Py_ssize_t hook_count
        for i in range(cycles):
            self._processor.clock()
        hook_count = len(self._tick_hooks)
        for hook_idx in range(hook_count):
            (<Component>self._tick_hooks[hook_idx]).on_cycles_elapsed(cycles)

    cpdef void run_for_microseconds(self, unsigned long microseconds, unsigned long cpu_hz):
        cdef unsigned long cycles = (microseconds * cpu_hz) // 1000000
        if cycles:
            self.run_cycles(cycles)

    cpdef void send_reset(self):
        self._processor.send_reset()

    cpdef Registers get_registers(self):
        return self._processor.get_registers()

    cpdef void set_registers(self, Registers registers):
        self._processor.set_registers(registers)

    def get_bus_values(self):
        return (
            self._current_bus_address,
            self._current_bus_data,
            self._current_bus_read_write_bar
        )

    # Wraparound disabled since address is strictly positive
    # Bounds checking disabled since short address is always within bus controller's address range
    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char read(self, unsigned short address):
        cdef MappedAddress mapped_address = self._component_address_map[address]

        self._current_bus_address = address
        self._current_bus_data = (<Component>mapped_address.component).read(mapped_address.internal_address)
        self._current_bus_read_write_bar = 1

        return self._current_bus_data

    # Wraparound disabled since address is strictly positive
    # Bounds checking disabled since short address is always within bus controller's address range
    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char write(self, unsigned short address, unsigned char data):
        cdef MappedAddress mapped_address = self._component_address_map[address]

        self._current_bus_address = address
        self._current_bus_data = (<Component>mapped_address.component).write(mapped_address.internal_address, data)
        self._current_bus_read_write_bar = 0

        return self._current_bus_data
