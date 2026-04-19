"""
Apple 1 display half of the 6821 PIA interface.

Register file (component-relative):
    offset 0 — DSP   ($D012 on the bus)
    offset 1 — DSPCR ($D013 on the bus)

DSP bit 7 is the "display busy" flag. On real hardware it stays high
for approximately one NTSC frame after a DSP write, which is what
throttles wozmon's output to ~60 chars/second. We preserve that timing
with a simple countdown that is serviced from the batch-end tick hook —
no per-cycle work on the CPU hot path. The countdown's initial value
is computed once at ``bind()`` time from the configured CPU frequency
(``round(cpu_hz / 60)`` — 60 Hz NTSC is hardcoded; PAL is not yet
plumbed through), so the timing follows ``cpu_hz`` rather than being
baked in at 1 MHz.
"""
from cython cimport boundscheck, wraparound
from importlib import resources

from py6502.sim.bus.component cimport Component
from py6502.sim.graphics.textdisplay cimport Font, TextDisplay


cdef float[4] BG_COLOR = [0x28 / 255.0, 0x28 / 255.0, 0x28 / 255.0, 1.0]
cdef float[4] FG_COLOR = [0x66 / 255.0, 1.0, 0x66 / 255.0, 1.0]

DEF DSP = 0x0000
DEF DSPCR = 0x0001
DEF DSP_BUSY = 0x80
DEF DSP_BUSY_FRAME_HZ = 60  # NTSC; PAL (50 Hz) not yet plumbed through


cdef class Apple1Display(Component):
    def __init__(self) -> None:
        super().__init__(2, "Apple1 Display")

        with resources.path('py6502.sim.assets.fonts', 'sphere-1.bin') as path:
            self._text_display = TextDisplay(256, 240, 8, 24, Font(str(path)))

        self._text_display.set_background_color(BG_COLOR)
        self._text_display.set_foreground_color(FG_COLOR)
        self._text_display.set_cursor(0x40, FG_COLOR, 1)
        self._text_display.clear_screen()

        self._busy_remaining = 0
        self._busy_cycles = 0

    cdef void bind(self, object system):
        system.register_tick_hook(self)
        self._busy_cycles = round(system.cpu_hz / DSP_BUSY_FRAME_HZ)

    @boundscheck(False)
    @wraparound(False)
    cdef int read(self, unsigned short address) except -1:
        if address == DSP:
            return DSP_BUSY if self._busy_remaining > 0 else 0x00
        return 0x00

    @boundscheck(False)
    @wraparound(False)
    cdef int write(self, unsigned short address, unsigned char data) except -1:
        cdef unsigned char stripped
        if address == DSP and self._busy_remaining <= 0:
            stripped = data & 0x7F
            if stripped == 0x0D:
                self._text_display.place_character(stripped)
            elif 0x20 <= stripped <= 0x5F:
                self._text_display.place_character(stripped)
            elif stripped >= 0x60:
                # Apple 1 charset quirk: 0x60-0x7F render as 0x40-0x5F.
                self._text_display.place_character(stripped - 0x20)
            self._busy_remaining = self._busy_cycles
        return data

    cdef void on_cycles_elapsed(self, unsigned long n):
        if self._busy_remaining > 0:
            self._busy_remaining -= <long>n

    cdef object get_framebuffer(self):
        return self._text_display.get_screen_buffer()

    cdef void render_framebuffer(self):
        self._text_display.render_framebuffer()
