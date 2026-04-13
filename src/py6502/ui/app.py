"""
Py6502App — DearPyGui shell that boots a configurable System preset and
renders video + debug panels at 60 Hz. v0.1 scope: one texture, one key
handler, one per-frame call into System, plus debug panels (registers +
memory monitor). System selector, disassembly, and binary loader land
later (see GH #8).
"""
from importlib import resources

import dearpygui.dearpygui as dpg

from py6502.sim.bus.emptyaddress import UnallocatedAddressError
from py6502.sim.cpu.mos6502 import InvalidOPCode
from py6502.sim.system import System
from py6502.ui.utils.instructionmaps import INSTRUCTION_MAP_6502
from py6502.ui.utils.keyhandler import KeyHandler
from py6502.ui.windows.video import VideoWindow


FRAME_MICROSECONDS = 16667
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
            width=VideoWindow.TEXTURE_WIDTH * 3 + DEBUG_WINDOW_WIDTH + 48,
            height=VideoWindow.TEXTURE_HEIGHT * 3 + 80,
        )
        dpg.setup_dearpygui()
        dpg.configure_app(init_file="./py6502ui.ini")
        dpg.set_exit_callback(self._save_init_file)

        self.system: System | None = None
        self._key_buffer: list[int] = []
        self._opcode_disasm = _build_opcode_disasm()
        self._mem_monitor_page = 0x00
        self._sim_running = True
        self._sim_error: str | None = None

        self._video = VideoWindow(self)
        self._video.build_texture_registry()
        self._build_menu_bar()
        self._video.build()
        self._build_debug_window()

        self._key_handler = KeyHandler(self._video, self._key_buffer)
        self._key_handler.build()

        dpg.show_viewport()
        dpg.set_primary_window(VideoWindow.VIDEO_WINDOW_TAG, True)

        self._load_default_system()
        self._refresh_debug_panels()

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------
    def _build_menu_bar(self) -> None:
        with dpg.viewport_menu_bar():
            with dpg.menu(label="File", tag="FileMenu"):
                dpg.add_menu_item(label="Reset System", tag="ResetMenuItem", callback=self._reset_system)
                dpg.add_separator(tag="FileMenuSeparator1")
                dpg.add_menu_item(label="Exit", tag="ExitMenuItem", callback=dpg.stop_dearpygui)
            with dpg.menu(label="Settings", tag="SettingsMenu"):
                dpg.add_menu_item(
                    label="Halt on invalid opcode",
                    tag="SettingsInvalidOpcode",
                    check=True,
                    default_value=True,
                    callback=self._on_invalid_opcode_toggle,
                )
                dpg.add_menu_item(
                    label="Halt on unmapped memory",
                    tag="SettingsUnmappedMemory",
                    check=True,
                    default_value=False,
                    callback=self._on_unmapped_memory_toggle,
                )
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About", callback=lambda: dpg.show_tool(dpg.mvTool_About))

    def _build_debug_window(self) -> None:
        with dpg.window(
            label="Debug",
            width=DEBUG_WINDOW_WIDTH,
            height=VideoWindow.TEXTURE_HEIGHT * 3 + 40,
            no_close=True,
            pos=(VideoWindow.TEXTURE_WIDTH * 3 + 24, 20),
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

            dpg.add_text("", tag="sim_error_text", color=(255, 0, 0), show=False)

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
                    try:
                        self.system.run_for_microseconds(FRAME_MICROSECONDS)
                    except (InvalidOPCode, UnallocatedAddressError) as exc:
                        self._on_sim_error(exc)
                    self._video.update_framebuffer(self.system.get_framebuffer())
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
        if not self.system.is_mapped(base):
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
        while self._key_buffer:
            if self.system.send_key(self._key_buffer[0]):
                self._key_buffer.pop(0)
            else:
                break

    def _on_sim_error(self, exc: Exception) -> None:
        self._sim_running = False
        self._sim_error = str(exc)
        dpg.set_value("sim_error_text", f"ERROR: {exc}")
        dpg.configure_item("sim_error_text", show=True)
        dpg.configure_item("play_button", enabled=False)
        dpg.configure_item("pause_button", enabled=False)

    def _on_invalid_opcode_toggle(self, sender, app_data, user_data) -> None:
        if self.system is not None:
            self.system.set_invalid_opcode_mode(1 if app_data else 0)

    def _on_unmapped_memory_toggle(self, sender, app_data, user_data) -> None:
        if self.system is not None:
            self.system.set_unmapped_memory_mode(app_data)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _play_handler(self) -> None:
        self._sim_running = True
        dpg.configure_item("play_button", enabled=False)
        dpg.configure_item("pause_button", enabled=True)
        dpg.focus_item(VideoWindow.VIDEO_WINDOW_TAG)

    def _pause_handler(self) -> None:
        self._sim_running = False
        dpg.configure_item("play_button", enabled=True)
        dpg.configure_item("pause_button", enabled=False)

    def _reset_handler(self) -> None:
        if self.system is None:
            return
        self.system.reset()
        self._key_buffer.clear()
        self._sim_error = None
        dpg.configure_item("sim_error_text", show=False)
        dpg.configure_item("play_button", enabled=True)
        dpg.configure_item("pause_button", enabled=True)
        self._play_handler()
        self._video.update_framebuffer(self.system.get_framebuffer())
        self._refresh_debug_panels()
        dpg.focus_item(VideoWindow.VIDEO_WINDOW_TAG)

    def _reset_system(self) -> None:
        self._reset_handler()

    def _save_init_file(self) -> None:
        dpg.save_init_file("./py6502ui.ini")
