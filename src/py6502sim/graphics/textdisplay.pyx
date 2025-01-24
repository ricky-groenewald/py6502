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
        cdef int offset = character * self.height * self.width
        return self.character_set[offset + y * self.width + x]

cdef class TextDisplay:
    def __init__(self, resolution_x, resolution_y, padding_x, padding_y, Font font):
        self._resolution_x = resolution_x
        self._resolution_y = resolution_y
        self._pixel_padding_x = padding_x
        self._pixel_padding_y = padding_y
        self._font = font
        self._cursor_visible = True
        self._cursor_size[:] = [0, 0, font.width, font.height]
        self._cursor_color[:] = [1.0, 1.0, 1.0, 1.0]
        self._cursor_x = 0
        self._cursor_y = 0
        self._screen_buffer = <float*>malloc(resolution_x * resolution_y * sizeof(float) * 4)
        self._background_color[:] = [0.0, 0.0, 0.0, 1.0]
        self._foreground_color[:] = [1.0, 1.0, 1.0, 1.0]

        self.clear_screen()

    def __dealloc__(self):
        if self._screen_buffer:
            free(self._screen_buffer)

    cpdef list get_screen_buffer(self):
        return [x for x in self._screen_buffer[:self._resolution_x * self._resolution_y * 4]]

    cdef void set_cursor_visible(self, bint cursor_visible):
        self._cursor_visible = cursor_visible

        # Draw / Remove cursor
        cdef int x_offset = self._cursor_x * self._font.width + self._pixel_padding_x
        cdef int y_offset = self._cursor_y * self._font.height + self._pixel_padding_y
        for j in range(self._font.height):
            for i in range(self._font.width):
                for rgba_index in range(4):
                    if (not (self._cursor_size[0] <= i < self._cursor_size[2])) or (not (self._cursor_size[1] <= j < self._cursor_size[3])) or (not self._cursor_visible):
                        self._screen_buffer[((y_offset + j) * self._resolution_x + x_offset + i) * 4 + rgba_index] = self._background_color[rgba_index]
                    else:
                        self._screen_buffer[((y_offset + j) * self._resolution_x + x_offset + i) * 4 + rgba_index] = self._cursor_color[rgba_index]

    cdef void place_character(self, unsigned char character):
        cdef int x_offset = self._cursor_x * self._font.width + self._pixel_padding_x
        cdef int y_offset = self._cursor_y * self._font.height + self._pixel_padding_y
        cdef unsigned char temp_character = 0

        if character == 0x0D or character == 0x08:
            temp_character = character
            character = 0x20
        elif character < 0x20:
            return

        # Draw character
        for j in range(self._font.height):
            for i in range(self._font.width):
                if self._font.get_character_pixel(character, i, j):
                    for rgba_index in range(4):
                        self._screen_buffer[((y_offset + j) * self._resolution_x + x_offset + i) * 4 + rgba_index] = self._foreground_color[rgba_index]
                else:
                    for rgba_index in range(4):
                        self._screen_buffer[((y_offset + j) * self._resolution_x + x_offset + i) * 4 + rgba_index] = self._background_color[rgba_index]

        # Increment cursor position and test x overflow
        if temp_character == 0x08:
            self._cursor_x -= 1
            if self._cursor_x == 0xff and self._cursor_y > 0:
                self._cursor_x = ((self._resolution_x - (self._pixel_padding_x * 2)) // self._font.width) - 1
                self._cursor_y -= 1
            elif self._cursor_x == 0xff:
                self._cursor_x = 0
        else:
            self._cursor_x += 1
            if (self._cursor_x * self._font.width + (self._pixel_padding_x * 2) >= self._resolution_x) or (temp_character == 0x0D):
                self._cursor_x = 0
                self._cursor_y += 1

        # Test cursor y overflow
        if self._cursor_y * self._font.height + (self._pixel_padding_y * 2) >= self._resolution_y:
            # Scroll all lines up by one cursor line
            for j in range(self._pixel_padding_y, self._resolution_y - self._pixel_padding_y - self._font.height):
                for i in range(self._pixel_padding_x, self._resolution_x - self._pixel_padding_x):
                    for rgba_index in range(4):
                        self._screen_buffer[((j * self._resolution_x + i) * 4) + rgba_index] = self._screen_buffer[(((j+self._font.height) * self._resolution_x + i) * 4) + rgba_index]
            
            # Clear last cursorline
            for j in range(self._resolution_y - self._pixel_padding_y - self._font.height, self._resolution_y - self._pixel_padding_y):
                for i in range(self._pixel_padding_x, self._resolution_x - self._pixel_padding_x):
                    for rgba_index in range(4):
                        self._screen_buffer[((j * self._resolution_x + i) * 4) + rgba_index] = self._background_color[rgba_index]

            self._cursor_y -= 1
            if temp_character == 0x0D:
                temp_character = 0x00

        # Redraw cursor (or not)
        self.set_cursor_visible(self._cursor_visible)

    cdef void cursor_backspace(self):
        self._cursor_x -= 1
        if self._cursor_x < 0:
            self._cursor_x = ((self._resolution_x - (self._pixel_padding_x * 2)) // self._font.width) - 1
            self._cursor_y -= 1
        
        # Redraw cursor (or not)
        self.set_cursor_visible(self._cursor_visible)

    cdef void clear_screen(self):
        for j in range(self._resolution_y):
            for i in range(self._resolution_x):
                for rgba_index in range(4):
                    self._screen_buffer[((j * self._resolution_x + i) * 4) + rgba_index] = self._background_color[rgba_index]

        self.set_cursor_visible(self._cursor_visible)

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
