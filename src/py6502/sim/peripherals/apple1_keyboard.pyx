"""
Apple 1 keyboard half of the 6821 PIA interface.

Register file (component-relative):
    offset 0 — KBD   ($D010 on the bus)
    offset 1 — KBDCR ($D011 on the bus)

Characters arrive with bit 7 set (Apple I convention). The buffer is a
circular FIFO. Backspace (0x08) is translated to underscore (0x5F) — the
Apple I rubout character — so wozmon handles it natively.
"""
from cython cimport boundscheck, wraparound
from libc.stdlib cimport malloc, free

from py6502.sim.bus.component cimport Component

DEF KBD = 0x0000
DEF KBDCR = 0x0001
DEF KBD_BUFFER_SIZE = 8


cdef class Apple1Keyboard(Component):
    def __init__(self) -> None:
        super().__init__(2, "Apple1 Keyboard")
        self._kbd_buffer = <unsigned char*>malloc(KBD_BUFFER_SIZE * sizeof(unsigned char))
        if self._kbd_buffer is NULL:
            raise MemoryError(f'[{self.get_name()}] Failed to allocate keyboard buffer')
        self._kbd_buffer_current_index = KBD_BUFFER_SIZE - 1
        self._kbd_buffer_last_index = 0

    def __dealloc__(self):
        if self._kbd_buffer is not NULL:
            free(self._kbd_buffer)

    cpdef bint add_character_to_kb_buffer(self, unsigned char char_):
        if self._kbd_buffer_current_index != self._kbd_buffer_last_index:
            # Apple I rubout: backspace → underscore.
            if char_ == 0x08:
                char_ = 0x5F
            # The Apple 1 keyboard controller expects bit 7 set on incoming chars.
            self._kbd_buffer[self._kbd_buffer_last_index] = char_ | 0x80
            self._kbd_buffer_last_index = (self._kbd_buffer_last_index + 1) % KBD_BUFFER_SIZE
            return True
        return False

    cpdef void clear_kbd_buffer(self):
        self._kbd_buffer_current_index = KBD_BUFFER_SIZE - 1
        self._kbd_buffer_last_index = 0

    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char read(self, unsigned short address) except *:
        if address == KBDCR and self._kbd_buffer_last_index != (self._kbd_buffer_current_index + 1) % KBD_BUFFER_SIZE:
            return 0x80
        if address == KBD and self._kbd_buffer_last_index != (self._kbd_buffer_current_index + 1) % KBD_BUFFER_SIZE:
            self._kbd_buffer_current_index = (self._kbd_buffer_current_index + 1) % KBD_BUFFER_SIZE
            return self._kbd_buffer[self._kbd_buffer_current_index]
        return 0x00

    @boundscheck(False)
    @wraparound(False)
    cdef unsigned char write(self, unsigned short address, unsigned char data) except *:
        return data
