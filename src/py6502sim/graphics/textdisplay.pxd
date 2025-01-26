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
    cdef bint _cursor_visible
    cdef unsigned char[4] _cursor_size # min_x, min_y, max_x, max_y
    cdef float[4] _cursor_color #RGBA
    cdef unsigned int _cursor_position
    cdef float* _screen_buffer
    cdef unsigned char* _character_buffer
    cdef unsigned char _character_max_cols
    cdef unsigned char _character_max_rows
    cdef unsigned int _character_buffer_size
    cdef unsigned int _character_buffer_start_index
    cdef unsigned int _character_buffer_end_index
    cdef unsigned char _character_line_count
    cdef unsigned char _character_current_line_start_index
    cdef float[4] _background_color #RGBA
    cdef float[4] _foreground_color #RGBA

    cdef void update_screen(self)
    cpdef list get_screen_buffer(self)
    cdef void set_cursor_visible(self, bint cursor_visible)
    cdef void set_cursor(self, unsigned char[4] size, float[4] color)
    cdef void place_character(self, unsigned char character)
    cdef void cursor_backspace(self)
    cdef void clear_screen(self)
    cdef void set_background_color(self, float[4] color)
    cdef void set_foreground_color(self, float[4] color)
