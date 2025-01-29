from libc.stdio cimport *
    
cdef class Font:
    cdef bint* character_set
    cdef unsigned char width
    cdef unsigned char height
    cdef unsigned char set_size

    cpdef void _create_character_set(self, char* filename) except *
    cdef bint get_character_pixel(self, unsigned char character, unsigned char x, unsigned char y)

cdef class TextDisplay:
    cdef Font _font
    cdef unsigned int _resolution_x
    cdef unsigned int _resolution_y
    cdef unsigned char _pixel_padding_x
    cdef unsigned char _pixel_padding_y
    cdef unsigned char _cursor_pos_x
    cdef unsigned char _cursor_pos_y
    cdef unsigned char _cursor_last_cr_y_pos
    cdef unsigned char _start_cursor_row
    cdef unsigned char _cursor_mode  # 0 = off, 1 = blinking, 2 = solid
    cdef unsigned char _cursor_blink_timer
    cdef bint _cursor_visible
    cdef unsigned char* _cursor_pixel_map
    cdef unsigned char[240][256] _screen_buffer # 240 rows, 256 columns
    cdef unsigned char _character_max_cols
    cdef unsigned char _character_max_rows
    cdef float[3][4] _colors #RGBA - 0 = background, 1 = foreground, 2 = cursor

    cpdef list get_screen_buffer(self)
    cdef void set_cursor(self, unsigned char[4] size, float[4] color, unsigned char cursor_mode)
    cdef void place_character(self, unsigned char character)
    cdef void clear_screen(self)
    cdef void set_background_color(self, float[4] color)
    cdef void set_foreground_color(self, float[4] color)
    cdef void redraw_cursor(self)
