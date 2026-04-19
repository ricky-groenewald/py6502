from libc.stdio cimport *
from cpython.array cimport array

cdef class Font:
    cdef bint* character_set
    cdef unsigned char width
    cdef unsigned char height
    cdef unsigned char set_size

    cdef void _create_character_set(self, char* filename) except *
    cdef inline bint get_character_pixel(self, unsigned char character, unsigned char x, unsigned char y)

cdef class TextDisplay:
    # See textdisplay.pyx for the field-by-field semantics; this header
    # only declares the storage. The 240×256 buffer is fixed-size on
    # purpose: it's contiguous, stack-shaped, and big enough for every
    # v0.1 display we ship. NES-era resolutions in v0.2 will use a
    # different graphics class entirely (this one is character-grid).
    cdef Font _font
    cdef unsigned int _resolution_x
    cdef unsigned int _resolution_y
    cdef unsigned char _pixel_padding_x
    cdef unsigned char _pixel_padding_y
    cdef unsigned char _cursor_pos_x
    cdef unsigned char _cursor_pos_y
    cdef unsigned char _cursor_last_cr_y_pos
    cdef unsigned char _start_cursor_row
    cdef unsigned char _cursor_mode
    cdef unsigned char _cursor_blink_timer
    cdef bint _cursor_visible
    cdef unsigned char* _cursor_pixel_map
    # _screen_buffer[y][x] — y is the row (0 = top of pixel space, not
    # of the unwrapped logical screen), x is the column. Values are
    # colour indices into _colors, not RGBA.
    cdef unsigned char[240][256] _screen_buffer
    cdef unsigned char _character_max_cols
    cdef unsigned char _character_max_rows
    # _colors[i] is RGBA. i=0 background, i=1 foreground, i=2 cursor.
    cdef float[3][4] _colors
    # RGBA output buffer (y-major, x-minor, RGBA last). Allocated once
    # and mutated in place so the frontend's bound raw texture never
    # sees a dangling or reassigned pointer. ``render_framebuffer``
    # ticks the cursor and flattens ``_screen_buffer`` into it once per
    # UI frame; ``get_screen_buffer`` is a pure ref getter.
    cdef array _rgba_buffer
    cdef float[::1] _rgba_view

    cdef object get_screen_buffer(self)
    cdef void render_framebuffer(self)
    cdef void set_cursor(self, unsigned char character, float[4] color, unsigned char cursor_mode)
    cdef void backspace(self)
    cdef void place_character(self, unsigned char character)
    cdef void clear_screen(self)
    cdef void set_background_color(self, float[4] color)
    cdef void set_foreground_color(self, float[4] color)
    cdef void redraw_cursor(self)
