"""
CYTHON CONTROLLER COMPONENT CLASS IMPLEMENTATIONS

The BusController is the heart of the address-routing layer. It owns a
flat 64K table of ``MappedAddress`` slots — one per 16-bit address —
each holding a raw ``PyObject*`` to the owning Component plus the
component-relative offset. A bus read/write is therefore one array
indexed lookup, one C cast, and one cdef virtual call into the
component — no Python attribute access, no list walk, no hash lookup.

Tick-hook fan-out is intentionally batched, not per-cycle: see
``run_cycles`` for the reasoning.
"""
from cpython.ref cimport PyObject, Py_INCREF, Py_DECREF
from cython cimport boundscheck, wraparound
from py6502.sim.bus.component cimport Component
from py6502.sim.bus.emptyaddress cimport EmptyAddress
from py6502.sim.bus.emptyaddress import UnallocatedAddressError
from py6502.sim.cpu.mos6502 cimport MOS6502, Registers, _mos6502_step

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
    Class definition for an 8-bit component controller.

    Holds the address→Component map and routes the CPU's reads/writes
    through it. Also owns the tick-hook list, so peripherals can hang
    cycle-accounting work off the end of every ``run_cycles`` batch
    without poking at the CPU hot path.
    """
    def __init__(self, str controller_name, MOS6502 processor, bint raise_on_unmapped_access=True) -> None:
        # Controllers always have a 16-bit address space — 0x10000 slots.
        super().__init__(0x10000, controller_name)
        self._processor = processor
        self._processor.set_memory_bus(self)
        self._current_bus_address = 0
        self._current_bus_data = 0
        self._current_bus_read_write_bar = 1
        self._tick_hooks = []
        # Every unmapped slot points at a single shared EmptyAddress
        # sentinel. We hand it a pointer to ``_current_bus_data`` so it
        # can return the last byte that was on the bus (open-bus
        # behaviour) when ``raise_on_unmapped_access`` is False.
        self._empty_address = EmptyAddress(
            'EmptyAddress',
            raise_on_unmapped_access
        )
        self._empty_address.set_bus_data_ptr(&self._current_bus_data)

        # The MappedAddress table stores raw PyObject* pointers — Python's
        # refcount machinery does not see them. We have to INCREF here for
        # every cell, and the matching DECREF lives in __dealloc__ (and,
        # per cell, in add_component when a real component takes over).
        for i in range(0x10000):
            self._component_address_map[i].component = <PyObject*>self._empty_address
            self._component_address_map[i].internal_address = i
            Py_INCREF(self._empty_address)

    def __dealloc__(self) -> None:
        for i in range(0x10000):
            if self._component_address_map[i].component is not NULL:
                Py_DECREF(<Component>self._component_address_map[i].component)
                self._component_address_map[i].component = NULL

    cdef void add_component(self, Component component, unsigned int address_start) except *:
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

        # Then map the addresses. Each cell's PyObject* slot is being
        # repointed from the shared EmptyAddress sentinel to the real
        # component, so refcount the swap by hand: INCREF the new owner,
        # DECREF the EmptyAddress slot we're displacing.
        for i in range(component.get_size()):
            self._component_address_map[address_start+i].internal_address = i
            self._component_address_map[address_start+i].component = <PyObject*>component
            Py_INCREF(component)
            Py_DECREF(self._empty_address)

    cdef void register_tick_hook(self, object component):
        """
        Subscribe a component to the batch-end tick hook. After every
        run_cycles(N) call, the component's on_cycles_elapsed(N) cdef
        method is invoked exactly once — not once per cycle.
        """
        self._tick_hooks.append(component)

    cdef int clock(self) except -1:
        self._processor.clock()
        return 0

    @boundscheck(False)
    @wraparound(False)
    cdef void run_cycles(self, unsigned long cycles) except *:
        # The hot loop. ``_mos6502_step`` is a free cdef function — calling
        # it directly skips the per-iteration vtable dispatch we'd pay
        # going through ``processor.clock()``.
        #
        # Tick hooks fire **once per batch**, not once per cycle, with the
        # batch size handed in. Peripherals that need cycle-accurate
        # timing (e.g. Apple1Display's DSP busy timer) keep their own
        # countdown and decrement by ``n`` in on_cycles_elapsed — that's
        # how we keep the steady-state loop entirely inside compiled C
        # while still giving the rest of the system a chance to breathe.
        cdef Py_ssize_t hook_idx
        cdef Py_ssize_t hook_count
        cdef MOS6502 processor = self._processor
        for _ in range(cycles):
            _mos6502_step(processor)
        hook_count = len(self._tick_hooks)
        for hook_idx in range(hook_count):
            (<Component>self._tick_hooks[hook_idx]).on_cycles_elapsed(cycles)

    cdef void run_for_microseconds(self, unsigned long microseconds, unsigned long cpu_hz) except *:
        cdef unsigned long cycles = (microseconds * cpu_hz) // 1000000
        if cycles:
            self.run_cycles(cycles)

    cdef void send_reset(self):
        self._processor.send_reset()

    cdef Registers get_registers(self):
        return self._processor.get_registers()

    cdef void set_registers(self, Registers registers):
        self._processor.set_registers(registers)

    cdef bint is_mapped(self, unsigned short address):
        return (<Component>self._component_address_map[address].component
                is not self._empty_address)

    cdef void set_unmapped_memory_mode(self, bint crash):
        self._empty_address._raise_on_unmapped = crash

    cdef tuple get_bus_values(self):
        return (
            self._current_bus_address,
            self._current_bus_data,
            self._current_bus_read_write_bar
        )

    # Wraparound disabled since address is strictly positive
    # Bounds checking disabled since short address is always within bus controller's address range
    @boundscheck(False)
    @wraparound(False)
    cdef int read(self, unsigned short address) except -1:
        cdef MappedAddress mapped_address = self._component_address_map[address]

        self._current_bus_address = address
        self._current_bus_data = <unsigned char>(<Component>mapped_address.component).read(mapped_address.internal_address)
        self._current_bus_read_write_bar = 1

        return self._current_bus_data

    # Wraparound disabled since address is strictly positive
    # Bounds checking disabled since short address is always within bus controller's address range
    @boundscheck(False)
    @wraparound(False)
    cdef int write(self, unsigned short address, unsigned char data) except -1:
        cdef MappedAddress mapped_address = self._component_address_map[address]

        self._current_bus_address = address
        self._current_bus_data = <unsigned char>(<Component>mapped_address.component).write(mapped_address.internal_address, data)
        self._current_bus_read_write_bar = 0

        return self._current_bus_data
