from libc.stdio cimport *
from libc.stdlib cimport malloc, free

cdef class Font:
    def __init__(self, filename):
        self._create_character_set(filename.encode('utf-8'))

    def __dealloc__(self):
        if self.character_set:
            free(self.character_set)

    cpdef void _create_character_set(self, char* filename) except *:
        cdef FILE* cfile = fopen(filename, "rb")
        if cfile == NULL:
            raise FileNotFoundError(f"File {filename} not found")

        fseek(cfile, 0, SEEK_END)
        cdef size_t file_size = ftell(cfile)
        fseek(cfile, 0, SEEK_SET)
        buffer = <unsigned char*>malloc(file_size * sizeof(unsigned char))
        fread(buffer, sizeof(unsigned char), file_size, cfile)
        fclose(cfile)

        self.width = (buffer[0] & 0xF0) >> 4
        self.height = buffer[0] & 0x0F
        self.set_size = <unsigned char>((file_size - 1) / (self.height * ((self.width + 7) // 8)))
        self.character_set = <bint*>malloc(self.set_size * sizeof(bint) * self.width * self.height)

        cdef int offset
        for char_num in range(self.set_size):
            for row in range(self.height):
                offset = char_num * self.height + row
                for col in range(self.width):
                    self.character_set[offset * self.width + col] = (buffer[offset + (col // 8)] >> (self.width - col - 1)) & 0x01

        free(buffer)

    cdef bint get_character_pixel(self, unsigned char character, unsigned char x, unsigned char y):
        return self.character_set[(character * self.height + y) * self.width + x]

cdef class TextDisplay:
    def __init__(self, resolution_x, resolution_y, padding_x, padding_y, Font font):
        # Basic screen setup
        self._resolution_x = resolution_x
        self._resolution_y = resolution_y
        self._screen_buffer = <float*>malloc(resolution_x * resolution_y * sizeof(float) * 4)
        self._pixel_padding_x = padding_x
        self._pixel_padding_y = padding_y
        self._font = font
        self._background_color[:] = [0.0, 0.0, 0.0, 1.0]
        self._foreground_color[:] = [1.0, 1.0, 1.0, 1.0]

        self._cursor_rgba = <float*>malloc(font.width * font.height * 4 * sizeof(float))
        self._cursor_pos_x = 0
        self._cursor_pos_y = 0
        self._cursor_last_cr_y_pos = 0
        self._start_cursor_row = 0
        self._cursor_mode = 1 # 0 = off, 1 = blinking, 2 = solid
        self._cursor_blink_timer = 0
        self._cursor_visible = True
        self._character_max_cols = (resolution_x - (padding_x * 2)) // font.width
        self._character_max_rows = (resolution_y - (padding_y * 2)) // font.height

        self.clear_screen()

    def __dealloc__(self):
        if self._screen_buffer:
            free(self._screen_buffer)

    cpdef list get_screen_buffer(self):
        if self._cursor_mode == 1:
            self._cursor_blink_timer += 1
            if self._cursor_blink_timer == 30:
                self._cursor_visible = not self._cursor_visible
                self._cursor_blink_timer = 0
                self.redraw_cursor()

        return (
            [x for x in self._screen_buffer[:self._resolution_x * self._pixel_padding_y * 4]] # Top padding
            + [x for x in self._screen_buffer[self._resolution_x * (self._start_cursor_row * self._font.height + self._pixel_padding_y) * 4:self._resolution_x * (self._resolution_y - self._pixel_padding_y) * 4]] # From content y-start to bottom padding
            + [x for x in self._screen_buffer[self._resolution_x * self._pixel_padding_y * 4:self._resolution_x * (self._start_cursor_row * self._font.height + self._pixel_padding_y) * 4]] # From top padding end to content y-start
            + [x for x in self._screen_buffer[:self._resolution_x * self._pixel_padding_y * 4]] # Bottom padding (Same as top padding)
        )

    cdef void place_character(self, unsigned char character):
        if character == 0x1B:
            return

        cdef int y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
        cdef int x_offset = self._pixel_padding_x + self._cursor_pos_x * self._font.width

        cdef int temp_offset, temp_cursor_offset
        if character == 0x0D: # CR
            for y in range(self._font.height):
                for x in range(self._font.width):
                    temp_offset = ((y_offset + y) * self._resolution_x + x_offset + x) * 4
                    self._screen_buffer[temp_offset] = self._background_color[0]
                    self._screen_buffer[temp_offset + 1] = self._background_color[1]
                    self._screen_buffer[temp_offset + 2] = self._background_color[2]
                    self._screen_buffer[temp_offset + 3] = self._background_color[3]

            self._cursor_pos_y = (self._cursor_pos_y + 1) % self._character_max_rows
            self._cursor_pos_x = 0
            self._cursor_last_cr_y_pos = self._cursor_pos_y

            if self._cursor_pos_y == self._start_cursor_row:
                # If cursor is at the top of the screen, scroll and clear cursor line
                self._start_cursor_row = (self._start_cursor_row + 1) % self._character_max_rows
                y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
                for y in range(self._font.height):
                    for x in range(self._pixel_padding_x, self._resolution_x - self._pixel_padding_x):
                        temp_offset = ((y_offset + y) * self._resolution_x + x) * 4
                        self._screen_buffer[temp_offset] = self._background_color[0]
                        self._screen_buffer[temp_offset + 1] = self._background_color[1]
                        self._screen_buffer[temp_offset + 2] = self._background_color[2]
                        self._screen_buffer[temp_offset + 3] = self._background_color[3]

        elif character == 0x08: # Backspace
            if self._cursor_pos_x == 0 and self._cursor_pos_y == self._cursor_last_cr_y_pos:
                # Can't backspace CR
                return

            for y in range(self._font.height):
                for x in range(self._font.width):
                    temp_offset = ((y_offset + y) * self._resolution_x + x_offset + x) * 4
                    self._screen_buffer[temp_offset] = self._background_color[0]
                    self._screen_buffer[temp_offset + 1] = self._background_color[1]
                    self._screen_buffer[temp_offset + 2] = self._background_color[2]
                    self._screen_buffer[temp_offset + 3] = self._background_color[3]
            
            if self._cursor_pos_x > 0:
                self._cursor_pos_x -= 1
            else:
                self._cursor_pos_x = self._character_max_cols - 1
                self._cursor_pos_y = (self._character_max_rows + self._cursor_pos_y - 1) % self._character_max_rows

        else: # Any other character
            for y in range(self._font.height):
                for x in range(self._font.width):
                    temp_offset = ((y_offset + y) * self._resolution_x + x_offset + x) * 4
                    if self._font.get_character_pixel(character, x, y):
                        self._screen_buffer[temp_offset] = self._foreground_color[0]
                        self._screen_buffer[temp_offset + 1] = self._foreground_color[1]
                        self._screen_buffer[temp_offset + 2] = self._foreground_color[2]
                        self._screen_buffer[temp_offset + 3] = self._foreground_color[3]
                    else:
                        self._screen_buffer[temp_offset] = self._background_color[0]
                        self._screen_buffer[temp_offset + 1] = self._background_color[1]
                        self._screen_buffer[temp_offset + 2] = self._background_color[2]
                        self._screen_buffer[temp_offset + 3] = self._background_color[3]

            self._cursor_pos_x = (self._cursor_pos_x + 1) % self._character_max_cols
            if self._cursor_pos_x == 0:
                self._cursor_pos_y = (self._cursor_pos_y + 1) % self._character_max_rows
                if self._cursor_pos_y == self._start_cursor_row:
                    # If cursor is at the top of the screen, scroll and clear cursor line
                    self._start_cursor_row = (self._start_cursor_row + 1) % self._character_max_rows
                    y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
                    for y in range(self._font.height):
                        for x in range(self._pixel_padding_x, self._resolution_x - self._pixel_padding_x):
                            temp_offset = ((y_offset + y) * self._resolution_x + x) * 4
                            self._screen_buffer[temp_offset] = self._background_color[0]
                            self._screen_buffer[temp_offset + 1] = self._background_color[1]
                            self._screen_buffer[temp_offset + 2] = self._background_color[2]
                            self._screen_buffer[temp_offset + 3] = self._background_color[3]

        # Draw cursor
        if self._cursor_mode:
            self._cursor_blink_timer = 0
            self._cursor_visible = True
            y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
            x_offset = self._pixel_padding_x + self._cursor_pos_x * self._font.width
            for y in range(self._font.height):
                for x in range(self._font.width):
                    temp_offset = ((y_offset + y) * self._resolution_x + x_offset + x) * 4
                    temp_cursor_offset = (y * self._font.width + x) * 4
                    self._screen_buffer[temp_offset] = self._cursor_rgba[temp_cursor_offset]
                    self._screen_buffer[temp_offset + 1] = self._cursor_rgba[temp_cursor_offset + 1]
                    self._screen_buffer[temp_offset + 2] = self._cursor_rgba[temp_cursor_offset + 2]
                    self._screen_buffer[temp_offset + 3] = self._cursor_rgba[temp_cursor_offset + 3]
        elif character == 0x08:
            self.redraw_cursor()

    cdef void clear_screen(self):
        cdef unsigned int offset
        for y in range(self._resolution_y):
            for x in range(self._resolution_x):
                offset = (y * self._resolution_x + x) * 4
                self._screen_buffer[offset] = self._background_color[0]
                self._screen_buffer[offset + 1] = self._background_color[1]
                self._screen_buffer[offset + 2] = self._background_color[2]
                self._screen_buffer[offset + 3] = self._background_color[3]

    cdef void set_background_color(self, float[4] color):
        for index in range(4):
            self._background_color[index] = color[index]

    cdef void set_foreground_color(self, float[4] color):
        for index in range(4):
            self._foreground_color[index] = color[index]

    cdef void redraw_cursor(self):
        cdef int y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
        cdef int x_offset = self._pixel_padding_x + self._cursor_pos_x * self._font.width
        cdef int temp_offset, temp_cursor_offset

        if self._cursor_visible:
            for y in range(self._font.height):
                for x in range(self._font.width):
                    temp_offset = ((y_offset + y) * self._resolution_x + x_offset + x) * 4
                    temp_cursor_offset = (y * self._font.width + x) * 4
                    self._screen_buffer[temp_offset] = self._cursor_rgba[temp_cursor_offset]
                    self._screen_buffer[temp_offset + 1] = self._cursor_rgba[temp_cursor_offset + 1]
                    self._screen_buffer[temp_offset + 2] = self._cursor_rgba[temp_cursor_offset + 2]
                    self._screen_buffer[temp_offset + 3] = self._cursor_rgba[temp_cursor_offset + 3]
        else:
            for y in range(self._font.height):
                for x in range(self._font.width):
                    temp_offset = ((y_offset + y) * self._resolution_x + x_offset + x) * 4
                    self._screen_buffer[temp_offset] = self._background_color[0]
                    self._screen_buffer[temp_offset + 1] = self._background_color[1]
                    self._screen_buffer[temp_offset + 2] = self._background_color[2]
                    self._screen_buffer[temp_offset + 3] = self._background_color[3]

    cdef void set_cursor(self, unsigned char[4] size, float[4] color, unsigned char cursor_mode):
        self._cursor_mode = cursor_mode
        if cursor_mode:
            self._cursor_blink_timer = 0
            self._cursor_visible = True
        else:
            self._cursor_visible = False

        for y in range(self._font.height):
            for x in range(self._font.width):
                if size[0] <= x < size[2] and size[1] <= y < size[3]:
                    self._cursor_rgba[(y * self._font.width + x) * 4] = color[0]
                    self._cursor_rgba[(y * self._font.width + x) * 4 + 1] = color[1]
                    self._cursor_rgba[(y * self._font.width + x) * 4 + 2] = color[2]
                    self._cursor_rgba[(y * self._font.width + x) * 4 + 3] = color[3]
                else:
                    self._cursor_rgba[(y * self._font.width + x) * 4] = self._background_color[0]
                    self._cursor_rgba[(y * self._font.width + x) * 4 + 1] = self._background_color[1]
                    self._cursor_rgba[(y * self._font.width + x) * 4 + 2] = self._background_color[2]
                    self._cursor_rgba[(y * self._font.width + x) * 4 + 3] = self._background_color[3]

        self.redraw_cursor()
