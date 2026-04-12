from py6502.sim.bus.component cimport Component
from py6502.sim.graphics.textdisplay cimport TextDisplay


cdef class Apple1Display(Component):
    cdef TextDisplay _text_display
    cdef long _busy_remaining

    cdef unsigned char read(self, unsigned short address) except *
    cdef unsigned char write(self, unsigned short address, unsigned char data) except *
    cdef void bind(self, object system)
    cdef void on_cycles_elapsed(self, unsigned long n)
    cdef list get_framebuffer(self)
