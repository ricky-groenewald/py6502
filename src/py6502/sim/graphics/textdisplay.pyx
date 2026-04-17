"""
TextDisplay + Font: a character-grid renderer with a vintage-style
blinking cursor and seamless scroll.

The Font wraps a tiny custom binary format we use to pack pixel-perfect
glyphs out of historical font ROMs. The TextDisplay treats its
``_screen_buffer`` as a circular row buffer so a scroll-up is just an
index rebase, not a memcpy.
"""
from libc.stdio cimport *
from libc.stdlib cimport malloc, free

cdef class Font:
    """
    Bitmap font, unpacked from a custom .bin format on construction.

    File layout:

        byte 0:    header
                     bits 7..4 — glyph width  in pixels (1..15)
                     bits 3..0 — glyph height in pixels (1..15)
        byte 1..:  glyph rows, packed MSB-first.
                   Each glyph occupies (height × ceil(width / 8)) bytes,
                   so a typical 8x8 glyph is 8 bytes (one byte per row,
                   one bit per pixel). Glyphs are stored in ASCII order
                   starting from whatever the font ROM started at —
                   character_set[N] is the Nth glyph in the file, the
                   caller is responsible for any mapping (Apple 1's
                   0x60..0x7F → 0x40..0x5F quirk lives in
                   Apple1Display, not here).

    The unpacked pixel grid is stored as a flat ``bint`` array indexed
    by ``(char * height + y) * width + x`` so per-pixel lookup at draw
    time is one multiply-add and one indirect load.
    """
    def __init__(self, filename):
        self._create_character_set(filename.encode('utf-8'))

    def __dealloc__(self):
        if self.character_set:
            free(self.character_set)

    cdef void _create_character_set(self, char* filename) except *:
        cdef FILE* cfile = fopen(filename, "rb")
        if cfile == NULL:
            raise FileNotFoundError(f"File {filename} not found")

        # Slurp the whole file. Fonts are tiny (the Apple 1 sphere font
        # is ~520 bytes), so a one-shot read beats streaming.
        fseek(cfile, 0, SEEK_END)
        cdef size_t file_size = ftell(cfile)
        fseek(cfile, 0, SEEK_SET)
        buffer = <unsigned char*>malloc(file_size * sizeof(unsigned char))
        fread(buffer, sizeof(unsigned char), file_size, cfile)
        fclose(cfile)

        # Unpack the header. ``set_size`` is derived from the remaining
        # bytes: each glyph takes height × ceil(width / 8) bytes.
        self.width = (buffer[0] & 0xF0) >> 4
        self.height = buffer[0] & 0x0F
        self.set_size = <unsigned char>((file_size - 1) / (self.height * ((self.width + 7) // 8)))
        self.character_set = <bint*>malloc(self.set_size * sizeof(bint) * self.width * self.height)

        # Unpack each packed glyph row into individual bits. The shift
        # ``width - col - 1`` walks pixels left-to-right because the
        # source bytes are MSB-first — the leftmost pixel is the high
        # bit of the row byte.
        cdef int offset
        for char_num in range(self.set_size):
            for row in range(self.height):
                offset = char_num * self.height + row
                for col in range(self.width):
                    self.character_set[offset * self.width + col] = (buffer[offset + (col // 8)] >> (self.width - col - 1)) & 0x01

        free(buffer)

    cdef inline bint get_character_pixel(self, unsigned char character, unsigned char x, unsigned char y):
        # Inlined into the renderer hot path: one indexed load per pixel.
        return self.character_set[(character * self.height + y) * self.width + x]

cdef class TextDisplay:
    """
    Character-grid framebuffer with a circular row-buffer for free
    scroll-up.

    State invariants worth knowing before touching this:

    - ``_screen_buffer[y][x]`` holds a *colour index* (0/1/2 — see
      ``_colors``), not a packed RGBA value. The RGBA expansion only
      happens in ``get_screen_buffer`` so we never carry around a 4×
      buffer.
    - ``_cursor_pos_(x|y)`` are *character* coordinates inside the
      visible grid, **not** pixel coordinates.
    - ``_start_cursor_row`` is the character-row index that the renderer
      treats as the top of the screen. When CR scrolls past the bottom,
      we just advance this index modulo ``_character_max_rows`` and
      clear the freshly-exposed line — no copy. ``get_screen_buffer``
      unwraps the rotation when it walks the buffer to RGBA.
    - ``_cursor_mode``: 0 = off, 1 = blinking, 2 = solid. The blinking
      timer cadence is 30 frames per phase (≈half a second at 60 FPS).
    - ``_cursor_pixel_map`` is the *unpacked* glyph for the cursor
      character, computed once in ``set_cursor`` so ``redraw_cursor``
      doesn't re-walk the font on every frame.
    """
    def __init__(self, resolution_x, resolution_y, padding_x, padding_y, Font font):
        # Basic screen setup
        self._resolution_x = resolution_x
        self._resolution_y = resolution_y
        self._pixel_padding_x = padding_x
        self._pixel_padding_y = padding_y
        self._font = font
        # _colors[0] = background, [1] = foreground, [2] = cursor.
        # Defaults are black/white/white; peripherals override via
        # set_background_color / set_foreground_color / set_cursor.
        self._colors[0] = [0.0, 0.0, 0.0, 1.0]
        self._colors[1] = [1.0, 1.0, 1.0, 1.0]
        self._colors[2] = [1.0, 1.0, 1.0, 1.0]
        for row in range(240):
            self._screen_buffer[row][:] = [0] * 256
        self._cursor_pos_x = 0
        self._cursor_pos_y = 0
        self._cursor_last_cr_y_pos = 0
        self._start_cursor_row = 0
        self._cursor_mode = 1
        self._cursor_blink_timer = 0
        self._cursor_visible = True
        self._cursor_pixel_map = <unsigned char*>malloc(font.width * font.height * sizeof(unsigned char))
        # Visible character-grid dimensions, with the padding stripped
        # off both sides — this is the cursor's actual playing field.
        self._character_max_cols = (resolution_x - (padding_x * 2)) // font.width
        self._character_max_rows = (resolution_y - (padding_y * 2)) // font.height

        self.clear_screen()

    def __dealloc__(self):
        if self._cursor_pixel_map:
            free(self._cursor_pixel_map)

    cdef list get_screen_buffer(self):
        # Tick the cursor blink (frame-paced, not cycle-paced — a "frame"
        # here is one call to this method, which the frontend invokes once
        # per UI frame).
        if self._cursor_mode == 1:
            self._cursor_blink_timer += 1
            if self._cursor_blink_timer == 30:
                self._cursor_visible = not self._cursor_visible
                self._cursor_blink_timer = 0

        self.redraw_cursor()

        # Flatten the buffer into a single RGBA-per-pixel list in screen
        # order: top padding band, then the *unwrapped* content (the
        # post-scroll rows that should appear at the top, then the
        # pre-scroll rows that should appear below them), then bottom
        # padding band. The two content slices together implement the
        # circular-buffer rotation without ever moving any pixels.
        return (
            [rgba_val for _ in range(self._pixel_padding_y) for _ in range(self._resolution_x) for rgba_val in self._colors[0][:4]] # Top padding band
            + [rgba_val for row in range(self._start_cursor_row * self._font.height + self._pixel_padding_y, self._resolution_y - self._pixel_padding_y) for col in range(self._resolution_x) for rgba_val in self._colors[self._screen_buffer[row][col]][:4]] # Rows from the scroll origin down to the bottom of the content area
            + [rgba_val for row in range(self._pixel_padding_y, self._start_cursor_row * self._font.height + self._pixel_padding_y) for col in range(self._resolution_x) for rgba_val in self._colors[self._screen_buffer[row][col]][:4]] # Rows from the top of the content area up to the scroll origin
            + [rgba_val for _ in range(self._pixel_padding_y) for _ in range(self._resolution_x) for rgba_val in self._colors[0][:4]] # Bottom padding band (same colour as top)
        )

    cdef void backspace(self):
        # Refuse to backspace past the start of the current input line
        # (the column-0 cell of the row that received the last CR). On
        # real Apple I hardware the backspace key is just an "underscore
        # back into the current cell"; we take the same liberty.
        if self._cursor_pos_x == 0 and self._cursor_pos_y == self._cursor_last_cr_y_pos:
            return

        cdef int y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
        cdef int x_offset = self._pixel_padding_x + self._cursor_pos_x * self._font.width

        # Wipe the cell the cursor is *currently* sitting in.
        for y in range(self._font.height):
            for x in range(self._font.width):
                self._screen_buffer[y_offset + y][x_offset + x] = 0

        # Move the cursor one cell to the left, wrapping to the previous
        # row if we were at column 0. The (max + y - 1) % max dance is
        # just modular subtraction that's safe for unsigned types.
        if self._cursor_pos_x > 0:
            self._cursor_pos_x -= 1
        else:
            self._cursor_pos_x = self._character_max_cols - 1
            self._cursor_pos_y = (self._character_max_rows + self._cursor_pos_y - 1) % self._character_max_rows

        # Reset the blink so the user can see exactly where the cursor
        # landed. blink_timer=28 ≈ "don't blink for ~half a phase".
        if self._cursor_mode:
            self._cursor_blink_timer = 28
            self._cursor_visible = False

    cdef void place_character(self, unsigned char character):
        cdef int y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
        cdef int x_offset = self._pixel_padding_x + self._cursor_pos_x * self._font.width

        if character == 0x0D: # CR
            # CR's contract here: clear the cell the cursor is on (so the
            # old cursor glyph doesn't linger on the previous line) and
            # advance to column 0 of the next row. Apple 1 had no LF —
            # CR did the work of both.
            for y in range(self._font.height):
                for x in range(self._font.width):
                    self._screen_buffer[y_offset + y][x_offset + x] = 0

            self._cursor_pos_y = (self._cursor_pos_y + 1) % self._character_max_rows
            self._cursor_pos_x = 0
            self._cursor_last_cr_y_pos = self._cursor_pos_y

            if self._cursor_pos_y == self._start_cursor_row:
                # We've wrapped into the row that's currently the visible
                # top — that's the scroll trigger. Bump _start_cursor_row
                # forward (which logically pushes the entire visible area
                # up by one row, see the docstring on the circular buffer)
                # and then clear what is now the bottom-most row so it
                # doesn't show stale content from before the scroll.
                self._start_cursor_row = (self._start_cursor_row + 1) % self._character_max_rows
                y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
                for y in range(self._font.height):
                    for x in range(self._pixel_padding_x, self._resolution_x - self._pixel_padding_x):
                        self._screen_buffer[y_offset + y][x] = 0

        else:
            # Normal printable character: stamp the glyph into the
            # current cell, advance the cursor, and scroll if we ran off
            # the right edge into the row that's currently the top.
            for y in range(self._font.height):
                for x in range(self._font.width):
                    self._screen_buffer[y_offset + y][x_offset + x] = self._font.get_character_pixel(character, x, y)

            self._cursor_pos_x = (self._cursor_pos_x + 1) % self._character_max_cols
            if self._cursor_pos_x == 0:
                self._cursor_pos_y = (self._cursor_pos_y + 1) % self._character_max_rows
                if self._cursor_pos_y == self._start_cursor_row:
                    # Same scroll path as the CR case above.
                    self._start_cursor_row = (self._start_cursor_row + 1) % self._character_max_rows
                    y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
                    for y in range(self._font.height):
                        for x in range(self._pixel_padding_x, self._resolution_x - self._pixel_padding_x):
                            self._screen_buffer[y_offset + y][x] = 0

        # Reset the blink (same reasoning as backspace).
        if self._cursor_mode:
            self._cursor_blink_timer = 28
            self._cursor_visible = False

    cdef void clear_screen(self):
        for y in range(self._resolution_y):
            for x in range(self._resolution_x):
                self._screen_buffer[y][x] = 0

    cdef void set_background_color(self, float[4] color):
        for index in range(4):
            self._colors[0][index] = color[index]

    cdef void set_foreground_color(self, float[4] color):
        for index in range(4):
            self._colors[1][index] = color[index]

    cdef void redraw_cursor(self):
        cdef int y_offset = self._pixel_padding_y + self._cursor_pos_y * self._font.height
        cdef int x_offset = self._pixel_padding_x + self._cursor_pos_x * self._font.width

        if self._cursor_visible:
            for y in range(self._font.height):
                for x in range(self._font.width):
                    self._screen_buffer[y_offset + y][x_offset + x] = self._cursor_pixel_map[y * self._font.width + x]
        else:
            for y in range(self._font.height):
                for x in range(self._font.width):
                    self._screen_buffer[y_offset + y][x_offset + x] = 0

    cdef void set_cursor(self, unsigned char character, float[4] color, unsigned char cursor_mode):
        self._cursor_mode = cursor_mode
        if cursor_mode:
            self._cursor_blink_timer = 0
            self._cursor_visible = True
        else:
            self._cursor_visible = False

        self._colors[2][:] = color

        for y in range(self._font.height):
            for x in range(self._font.width):
                self._cursor_pixel_map[y * self._font.width + x] = 2 if self._font.get_character_pixel(character, x, y) else 0
