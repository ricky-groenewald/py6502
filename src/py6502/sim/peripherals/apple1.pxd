from py6502.sim.bus.component cimport Component
from py6502.sim.bus.buscontroller cimport BusController
from py6502.sim.graphics.textdisplay cimport Font, TextDisplay

# Colors:
#   bg='#282828',
#   fg='#66FF66',

cdef class Apple1(Component):
    cdef TextDisplay _text_display
    cdef unsigned char* _kbd_buffer
    cdef unsigned char _kbd_buffer_index
    cdef unsigned char _display_status
    cdef BusController _bus_controller
    cpdef void initialize_display(self)
    cpdef bint add_character_to_kb_buffer(self, unsigned char character)
    cpdef void clear_kbd_buffer(self)
    cpdef void clock(self)