from py6502.sim.bus.component cimport Component


cdef class Apple1Keyboard(Component):
    cdef unsigned char* _kbd_buffer
    cdef unsigned char _kbd_buffer_current_index
    cdef unsigned char _kbd_buffer_last_index

    cdef unsigned char read(self, unsigned short address)
    cdef unsigned char write(self, unsigned short address, unsigned char data)
    cpdef bint add_character_to_kb_buffer(self, unsigned char char_)
    cpdef void clear_kbd_buffer(self)
