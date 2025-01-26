from libc.stdio cimport *
from libc.stdlib cimport malloc, free

cdef class Font:
    def __init__(self, filename, blank_zero=False):
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

        # Cursor setup
        self._cursor_visible = True
        self._cursor_size[:] = [0, 0, font.width, font.height]
        self._cursor_color[:] = [1.0, 1.0, 1.0, 1.0]
        self._cursor_position = 0

        # Character buffer setup
        self._character_max_cols = (resolution_x - (padding_x * 2)) // font.width
        self._character_max_rows = (resolution_y - (padding_y * 2)) // font.height
        self._character_buffer_size = self._character_max_cols * self._character_max_rows
        self._character_buffer_start_index = 0
        self._character_buffer_end_index = 0
        self._character_buffer = <unsigned char*>malloc(self._character_buffer_size * sizeof(unsigned char))
        self._character_line_count = 0

        self.clear_screen()

    def __dealloc__(self):
        if self._screen_buffer:
            free(self._screen_buffer)

    cdef void update_screen(self):
        cdef int character_index = self._character_buffer_start_index

        for y in range(self._pixel_padding_y, self._resolution_y - self._pixel_padding_y, self._font.height):
            for x in range(self._pixel_padding_x, self._resolution_x - self._pixel_padding_x):
                if (self._character_buffer[character_index] == 0x0D) or (character_index == self._character_buffer_end_index):
                    for i in range(x, self._resolution_x - self._pixel_padding_x):
                        for j in range(y, y + self._font.height):
                            for rgba_index in range(4):
                                self._screen_buffer[((j * self._resolution_x) + i) * 4 + rgba_index] = self._background_color[rgba_index]

                    if self._character_buffer[character_index] == 0x0D:
                        character_index = (character_index + 1) % self._character_buffer_size
                    break

                for j in range(self._font.height):
                    if self._font.get_character_pixel(self._character_buffer[character_index], (x - self._pixel_padding_x) % self._font.width, j):
                        for rgba_index in range(4):
                            self._screen_buffer[(((y + j) * self._resolution_x) + x) * 4 + rgba_index] = self._foreground_color[rgba_index]
                    else:
                        for rgba_index in range(4):
                            self._screen_buffer[(((y + j) * self._resolution_x) + x) * 4 + rgba_index] = self._background_color[rgba_index]
                
                if (x - self._pixel_padding_x) % self._font.width == self._font.width - 1:
                    character_index = (character_index + 1) % self._character_buffer_size

        # Draw cursor
        cdef int x_offset = self._character_buffer_end_index - self._character_current_line_start_index
        if x_offset < 0:
            x_offset += self._character_buffer_size
        x_offset = x_offset * self._font.width + self._pixel_padding_x
        cdef int y_offset = self._character_line_count * self._font.height + self._pixel_padding_y
        if self._cursor_visible:
            for i in range(x_offset, x_offset + self._font.width):
                for j in range(y_offset, y_offset + self._font.height):
                    if self._cursor_size[0] <= ((i - self._pixel_padding_x) % self._font.width) <= self._cursor_size[2] and self._cursor_size[1] <= ((j - self._pixel_padding_y) % self._font.height) <= self._cursor_size[3]:
                        for rgba_index in range(4):
                            self._screen_buffer[(((j * self._resolution_x) + i) * 4) + rgba_index] = self._cursor_color[rgba_index]
                    else:
                        for rgba_index in range(4):
                            self._screen_buffer[(((j * self._resolution_x) + i) * 4) + rgba_index] = self._background_color[rgba_index]

    cpdef list get_screen_buffer(self):
        return [x for x in self._screen_buffer[:self._resolution_x * self._resolution_y * 4]]

    cdef void set_cursor_visible(self, bint cursor_visible):
        self._cursor_visible = cursor_visible

    cdef void place_character(self, unsigned char character):
        if character == 0x08:
            self.cursor_backspace()
            return
        elif character == 0x1B:
            return

        self._character_buffer[self._character_buffer_end_index] = character
        self._character_buffer_end_index = (self._character_buffer_end_index + 1) % self._character_buffer_size
        if character == 0x0D:
            # Handle new line
            self._character_line_count += 1
            self._character_current_line_start_index = self._character_buffer_end_index
        else:
            # Check for line wrap
            if self._character_buffer_end_index < self._character_current_line_start_index:
                if self._character_buffer_end_index + self._character_buffer_size - self._character_current_line_start_index == self._character_max_cols:
                    self._character_line_count += 1
                    self._character_current_line_start_index = self._character_buffer_end_index
            else:
                if self._character_buffer_end_index - self._character_current_line_start_index == self._character_max_cols:
                    self._character_line_count += 1
                    self._character_current_line_start_index = self._character_buffer_end_index

        if self._character_line_count == self._character_max_rows:
            # If line count is maxed out, move start index to next line
            self._character_line_count -= 1

            # Find the next line wrap or CR, whichever comes first
            for index in range(self._character_buffer_start_index, self._character_buffer_start_index + self._character_max_cols):
                if self._character_buffer[index % self._character_buffer_size] == 0x0D:
                    break
            self._character_buffer_start_index = (index + 1) % self._character_buffer_size

    cdef void cursor_backspace(self):
        if (self._character_buffer_end_index == self._character_buffer_start_index) and not self._character_line_count:
            # Screen is empty, do nothing
            return

        cdef previous_index = (self._character_buffer_size + self._character_buffer_end_index - 1) % self._character_buffer_size
        if self._character_buffer[previous_index] != 0x0D:
            if self._character_buffer_end_index == self._character_current_line_start_index:
                self._character_line_count -= 1
                # Find previous line wrap or CR, whichever comes first
                for index in range(1, self._character_max_cols + 1):
                    if self._character_buffer[(self._character_current_line_start_index + self._character_buffer_size - index) % self._character_buffer_size] == 0x0D:
                        break
                self._character_current_line_start_index = (self._character_current_line_start_index + self._character_buffer_size - index) % self._character_buffer_size
            self._character_buffer_end_index = previous_index
        # else:
            # Can't backspace CR
            # pass
        

    cdef void clear_screen(self):
        self._character_buffer_start_index = 0
        self._character_buffer_end_index = 0
        self._character_line_count = 0

    cdef void set_background_color(self, float[4] color):
        for index in range(4):
            self._background_color[index] = color[index]

    cdef void set_foreground_color(self, float[4] color):
        for index in range(4):
            self._foreground_color[index] = color[index]

    cdef void set_cursor(self, unsigned char[4] size, float[4] color):
        for index in range(4):
            self._cursor_size[index] = size[index]
            self._cursor_color[index] = color[index]
