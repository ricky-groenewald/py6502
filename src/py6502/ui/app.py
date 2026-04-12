"""
Py6502App — minimal DearPyGui shell that boots the Apple I preset into
wozmon. v0.1 scope: one texture, one key handler, one per-frame call
into System, plus two debug panels (registers + memory monitor) ported
from the legacy py6502ui.py so the sim is actually inspectable while
wozmon boots. System selector, disassembly, and binary loader land
later (see GH #8).
"""
from importlib import resources

import dearpygui.dearpygui as dpg

from py6502.sim.bus.emptyaddress import UnallocatedAddressError
from py6502.sim.system import System
from py6502.ui.utils.instructionmaps import INSTRUCTION_MAP_6502


FRAME_MICROSECONDS = 16667
TEXTURE_WIDTH = 256
TEXTURE_HEIGHT = 240
TEXTURE_TAG = "output_texture"
VIDEO_WINDOW_TAG = "VideoOutputWindow"
DEBUG_WINDOW_TAG = "DebugWindow"
DEBUG_WINDOW_WIDTH = 480

ADDRESSING_MODES = [
    "imm", "abs", "zp", "acc", "imp",
    "(ind,X)", "(ind),Y", "zp,X", "abs,X", "abs,Y",
    "rel", "(ind)", "zp,Y",
]


def _build_opcode_disasm() -> dict[int, str]:
    disasm: dict[int, str] = {}
    for mnemonic, encodings in INSTRUCTION_MAP_6502.items():
        for i, opcode in enumerate(encodings):
            if opcode is not None:
                disasm[opcode] = f"{mnemonic} {ADDRESSING_MODES[i]}"
    return disasm


class Py6502App:
    def __init__(self) -> None:
        self.context = dpg.create_context()
        self.viewport = dpg.create_viewport(
            title="Py6502",
            width=TEXTURE_WIDTH * 3 + DEBUG_WINDOW_WIDTH + 48,
            height=TEXTURE_HEIGHT * 3 + 80,
        )
        dpg.setup_dearpygui()
        dpg.configure_app(init_file="./py6502ui.ini")
        dpg.set_exit_callback(self._save_init_file)

        self.system: System | None = None
        self._key_buffer: list[int] = []
        self._opcode_disasm = _build_opcode_disasm()
        self._mem_monitor_page = 0x00
        self._sim_running = True

        self._build_texture_registry()
        self._build_menu_bar()
        self._build_video_window()
        self._build_debug_window()
        self._build_key_handler()

        dpg.show_viewport()
        dpg.set_primary_window(VIDEO_WINDOW_TAG, True)

        self._load_default_system()
        self._refresh_debug_panels()

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------
    def _build_texture_registry(self) -> None:
        initial = [0.0] * (TEXTURE_WIDTH * TEXTURE_HEIGHT * 4)
        with dpg.texture_registry(show=False):
            dpg.add_dynamic_texture(TEXTURE_WIDTH, TEXTURE_HEIGHT, initial, tag=TEXTURE_TAG)

    def _build_menu_bar(self) -> None:
        with dpg.viewport_menu_bar():
            with dpg.menu(label="File", tag="FileMenu"):
                dpg.add_menu_item(label="Reset System", tag="ResetMenuItem", callback=self._reset_system)
                dpg.add_separator(tag="FileMenuSeparator1")
                dpg.add_menu_item(label="Exit", tag="ExitMenuItem", callback=dpg.stop_dearpygui)
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About", callback=lambda: dpg.show_tool(dpg.mvTool_About))

    def _build_video_window(self) -> None:
        with dpg.window(
            label="Video Output",
            width=TEXTURE_WIDTH * 3 + 16,
            height=TEXTURE_HEIGHT * 3 + 16,
            no_resize=True,
            no_close=True,
            no_title_bar=True,
            tag=VIDEO_WINDOW_TAG,
        ):
            dpg.draw_image(
                TEXTURE_TAG,
                (0, 20),
                (TEXTURE_WIDTH * 3, TEXTURE_HEIGHT * 3 + 1),
            )

    def _build_debug_window(self) -> None:
        with dpg.window(
            label="Debug",
            width=DEBUG_WINDOW_WIDTH,
            height=TEXTURE_HEIGHT * 3 + 40,
            no_close=True,
            pos=(TEXTURE_WIDTH * 3 + 24, 20),
            tag=DEBUG_WINDOW_TAG,
        ):
            with dpg.group(horizontal=True):
                dpg.add_button(label="Play", callback=self._play_handler, enabled=False, tag="play_button")
                dpg.add_button(label="Pause", callback=self._pause_handler, enabled=True, tag="pause_button")
                dpg.add_button(label="Reset", callback=self._reset_handler, tag="reset_button")
            dpg.add_separator()
            dpg.add_text("CPU Registers", color=(255, 255, 0))
            with dpg.group(horizontal=True):
                dpg.add_text("PC:"); dpg.add_text("0000", tag="reg_pc")
                dpg.add_text("  A:"); dpg.add_text("00", tag="reg_a")
                dpg.add_text("  X:"); dpg.add_text("00", tag="reg_x")
                dpg.add_text("  Y:"); dpg.add_text("00", tag="reg_y")
                dpg.add_text("  S:"); dpg.add_text("00", tag="reg_s")
            with dpg.group(horizontal=True):
                dpg.add_text("Status:")
                dpg.add_text("N:0", tag="status_n_flag")
                dpg.add_text("V:0", tag="status_v_flag")
                dpg.add_text("B:0", tag="status_b_flag")
                dpg.add_text("D:0", tag="status_d_flag")
                dpg.add_text("I:0", tag="status_i_flag")
                dpg.add_text("Z:0", tag="status_z_flag")
                dpg.add_text("C:0", tag="status_c_flag")
            with dpg.group(horizontal=True):
                dpg.add_text("Opcode:")
                dpg.add_text("00", tag="reg_opcode")
                dpg.add_text("@")
                dpg.add_text("0000", tag="reg_opcode_addr")
            with dpg.group(horizontal=True):
                dpg.add_text("Decode:")
                dpg.add_text("", tag="reg_opcode_disasm")

            dpg.add_separator()
            dpg.add_text("Memory Monitor", color=(255, 255, 0))
            with dpg.group(horizontal=True, horizontal_spacing=0):
                dpg.add_text("Page: 0x")
                dpg.add_input_text(
                    tag="mem_page_input",
                    default_value="00",
                    width=32,
                    callback=self._on_mem_page_changed,
                    uppercase=True,
                    hexadecimal=True,
                    no_spaces=True,
                )
                dpg.add_text("00 ~ 0xFFxx")
            dpg.add_text("", tag="mem_monitor")

    def _build_key_handler(self) -> None:
        with dpg.handler_registry():
            dpg.add_key_press_handler(key=dpg.mvKey_None, callback=self._on_key_press)

    def _load_default_system(self) -> None:
        preset = resources.files("py6502.sim.assets").joinpath("presets/apple1.yaml")
        self.system = System.from_yaml_file(preset)

    # ------------------------------------------------------------------
    # Per-frame loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        while dpg.is_dearpygui_running():
            if self.system is not None:
                if self._sim_running:
                    self._drain_keys_into_system()
                    self.system.run_for_microseconds(FRAME_MICROSECONDS)
                    dpg.set_value(TEXTURE_TAG, self.system.get_framebuffer())
                self._refresh_debug_panels()
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

    def _refresh_debug_panels(self) -> None:
        if self.system is None:
            return
        self._update_registers()
        self._update_memory_monitor()

    def _update_registers(self) -> None:
        regs = self.system.get_registers()
        dpg.set_value("reg_pc", f"{regs['PC']:04X}")
        dpg.set_value("reg_a", f"{regs['ACC']:02X}")
        dpg.set_value("reg_x", f"{regs['X']:02X}")
        dpg.set_value("reg_y", f"{regs['Y']:02X}")
        dpg.set_value("reg_s", f"{regs['S']:02X}")
        p = regs["P"]
        dpg.set_value("status_n_flag", f"N:{(p >> 7) & 1}")
        dpg.set_value("status_v_flag", f"V:{(p >> 6) & 1}")
        dpg.set_value("status_b_flag", f"B:{(p >> 4) & 1}")
        dpg.set_value("status_d_flag", f"D:{(p >> 3) & 1}")
        dpg.set_value("status_i_flag", f"I:{(p >> 2) & 1}")
        dpg.set_value("status_z_flag", f"Z:{(p >> 1) & 1}")
        dpg.set_value("status_c_flag", f"C:{p & 1}")
        opcode = regs["OPCODE"]
        dpg.set_value("reg_opcode", f"{opcode:02X}")
        dpg.set_value("reg_opcode_addr", f"{regs['OPCODE_ADDR']:04X}")
        dpg.set_value("reg_opcode_disasm", self._opcode_disasm.get(opcode, "???"))

    def _update_memory_monitor(self) -> None:
        page = self._mem_monitor_page
        base = page << 8
        lines: list[str] = []
        try:
            first_byte = self.system.peek(base)
        except UnallocatedAddressError:
            dpg.set_value("mem_monitor", f"{base:04X}: Unmapped memory range")
            dpg.configure_item("mem_monitor", color=(255, 0, 0))
            return
        dpg.configure_item("mem_monitor", color=(255, 255, 255))
        for row in range(0, 0x100, 16):
            addr = base + row
            row_bytes = [self.system.peek(addr + i) for i in range(16)]
            left = " ".join(f"{b:02X}" for b in row_bytes[:8])
            right = " ".join(f"{b:02X}" for b in row_bytes[8:])
            ascii_repr = "".join(
                chr(b) if 0x20 <= b <= 0x7E else "." for b in row_bytes
            )
            lines.append(f"{addr:04X}: {left}  {right}  |{ascii_repr}|")
        dpg.set_value("mem_monitor", "\n".join(lines))

    def _on_mem_page_changed(self, sender, app_data, user_data) -> None:
        try:
            value = int(app_data, 16)
        except ValueError:
            dpg.set_value("mem_page_input", f"{self._mem_monitor_page:02X}")
            return
        if not 0 <= value <= 0xFF:
            dpg.set_value("mem_page_input", f"{self._mem_monitor_page:02X}")
            return
        self._mem_monitor_page = value
        dpg.set_value("mem_page_input", f"{value:02X}")
        if self.system is not None:
            self._update_memory_monitor()

    def _drain_keys_into_system(self) -> None:
        if not self.system.inputs:
            self._key_buffer.clear()
            return
        keyboard = self.system.inputs[0]
        while self._key_buffer:
            if keyboard.add_character_to_kb_buffer(self._key_buffer[0]):
                self._key_buffer.pop(0)
            else:
                break

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _play_handler(self) -> None:
        self._sim_running = True
        dpg.configure_item("play_button", enabled=False)
        dpg.configure_item("pause_button", enabled=True)

    def _pause_handler(self) -> None:
        self._sim_running = False
        dpg.configure_item("play_button", enabled=True)
        dpg.configure_item("pause_button", enabled=False)

    def _reset_handler(self) -> None:
        if self.system is None:
            return
        self.system.reset()
        self._key_buffer.clear()
        dpg.set_value(TEXTURE_TAG, self.system.get_framebuffer())
        self._refresh_debug_panels()

    def _reset_system(self) -> None:
        # Menu-bar entry; forwards to the main reset handler.
        self._reset_handler()

    def _save_init_file(self) -> None:
        dpg.save_init_file("./py6502ui.ini")

    def _on_key_press(self, sender, app_data, user_data) -> None:
        if self.system is None:
            return

        shift_down = dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)

        if app_data == dpg.mvKey_Return:
            self._key_buffer.append(0x0D)
            return
        if app_data == dpg.mvKey_Back:
            self._key_buffer.append(0x08)
            return
        if app_data == dpg.mvKey_Escape:
            self._key_buffer.append(0x1B)
            return

        char = _key_to_char(app_data, shift_down)
        if char is not None:
            self._key_buffer.append(ord(char))


def _key_to_char(app_data: int, shift_down: bool) -> str | None:
    """
    Translate a DearPyGui key code into the Apple I's ASCII character
    set. Returns None for unknown keys.
    """
    if dpg.mvKey_A <= app_data <= dpg.mvKey_Z:
        return chr(app_data - dpg.mvKey_A + ord('A'))
    if dpg.mvKey_0 <= app_data <= dpg.mvKey_9:
        if shift_down:
            return ")!@#$%^&*("[app_data - dpg.mvKey_0]
        return chr(app_data - dpg.mvKey_0 + ord('0'))
    if app_data == dpg.mvKey_Spacebar:
        return ' '
    if app_data == dpg.mvKey_Comma:
        return '<' if shift_down else ','
    if app_data == dpg.mvKey_Period:
        return '>' if shift_down else '.'
    if app_data == dpg.mvKey_Slash:
        return '?' if shift_down else '/'
    if app_data == 601:
        return ':' if shift_down else ';'
    if app_data == 596:
        return '"' if shift_down else "'"
    if app_data == dpg.mvKey_Open_Brace:
        return '{' if shift_down else '['
    if app_data == dpg.mvKey_Close_Brace:
        return '}' if shift_down else ']'
    if app_data == dpg.mvKey_Backslash:
        return '|' if shift_down else '\\'
    if app_data == dpg.mvKey_Minus:
        return '_' if shift_down else '-'
    if app_data == 602:
        return '+' if shift_down else '='
    if app_data == 606:
        return '~' if shift_down else '`'
    return None
