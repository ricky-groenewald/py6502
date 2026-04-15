from py6502.sim.bus.component cimport Component
from py6502.sim.graphics.textdisplay cimport TextDisplay


cdef class Apple1Display(Component):
    cdef TextDisplay _text_display
    cdef long _busy_remaining

    cdef int read(self, unsigned short address) except -1
    cdef int write(self, unsigned short address, unsigned char data) except -1
    cdef void bind(self, object system)
    cdef void on_cycles_elapsed(self, unsigned long n)
    cdef list get_framebuffer(self)
