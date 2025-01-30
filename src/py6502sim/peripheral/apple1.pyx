from py6502sim.bus.component cimport Component
from py6502sim.bus.buscontroller cimport BusController
from py6502sim.graphics.textdisplay cimport Font, TextDisplay
from importlib import resources
from libc.string cimport memcpy
from cython cimport boundscheck, wraparound
from libc.stdlib cimport malloc, free
# Colors:
#   bg='#282828',
#   fg='#66FF66',
cdef float[4] BG_COLOR = [0x28 / 255.0, 0x28 / 255.0, 0x28 / 255.0, 1.0]
cdef float[4] FG_COLOR = [0x66 / 255.0, 1.0, 0x66 / 255.0, 1.0]

DEF KBD = 0x0000
DEF KBDCR = 0x0001
DEF DSP = 0x0002
DEF DSPCR = 0x0003

DEF KBD_BUFFER_SIZE = 8
DEF FRAME_SIZE = 256 * 240

cdef class Apple1(Component):
    def __init__(self, str memory_name, BusController bus_controller) -> None:
        super().__init__(4, memory_name)

        with resources.path('py6502sim.assets.fonts', 'sphere-1.bin') as path:
            self._text_display = TextDisplay(256, 240, 8, 8, Font(str(path)))

        self.initialize_display()
        self._kbd_buffer_index = 0
        self._kbd_buffer = <unsigned char*>malloc(KBD_BUFFER_SIZE * sizeof(unsigned char))
        self._bus_controller = bus_controller

    def __dealloc__(self):
        if self._kbd_buffer:
            free(self._kbd_buffer)

    cpdef void clock(self):
        for _ in range(16667):
            self._bus_controller.clock()

    cpdef void initialize_display(self):
        self._text_display.set_background_color(BG_COLOR)
        self._text_display.set_foreground_color(FG_COLOR)
        self._text_display.set_cursor([0, 1, 5, 8], FG_COLOR, 1)
        self._text_display.clear_screen()

    cpdef bint add_character_to_kb_buffer(self, unsigned char character):
        if self._kbd_buffer_index < KBD_BUFFER_SIZE:
            self._kbd_buffer[self._kbd_buffer_index] = character | 0x80 # Apple 1 keyboard controller expects 0x80 to be set
            self._kbd_buffer_index += 1
            return True
        return False

    cpdef void clear_kbd_buffer(self):
        self._kbd_buffer_index = 0

    def get_screen_buffer(self):
        return self._text_display.get_screen_buffer()

    # Wraparound disabled since address is strictly positive
    # Bounds checking disabled since _read should only ever be accessed through "execute"
    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char _read(self, unsigned int address):
        if address == KBDCR and self._kbd_buffer_index:
                return 0x80
        elif address == KBD and self._kbd_buffer_index:
                self._kbd_buffer_index -= 1
                return self._kbd_buffer[self._kbd_buffer_index]
        else:
            return 0x00

    # Wraparound disabled since address is strictly positive
    # Bounds checking disabled since _read should only ever be accessed through "execute"
    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char _write(self, unsigned int address, unsigned char data):
        if address == DSP and data >= 0x80:
            self._text_display.place_character(data & 0x7F)

        return data
