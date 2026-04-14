"""Debug panel — emulator controls, CPU registers, opcode decode, and memory monitor."""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from py6502.sim.bus.emptyaddress import UnallocatedAddressError
from py6502.sim.cpu.mos6502 import InvalidOPCode
from py6502.ui.utils.instructionmaps import INSTRUCTION_MAP_6502
from py6502.ui.windows.video import VideoWindow

if TYPE_CHECKING:
    from py6502.sim.system import System
    from py6502.ui.app import Py6502App

ADDRESSING_MODES = [
    "imm", "abs", "zp", "acc", "imp",
    "(ind,X)", "(ind),Y", "zp,X", "abs,X", "abs,Y",
    "rel", "(ind)", "zp,Y",
]

WINDOW_TAG = "DebugWindow"

# Button tags
PLAY_BUTTON_TAG = "PlayButton"
PAUSE_BUTTON_TAG = "PauseButton"
INST_STEP_BUTTON_TAG = "InstStepButton"
CYCLE_STEP_BUTTON_TAG = "CycleStepButton"
RESET_BUTTON_TAG = "ResetButton"

# Register tags
REG_PC_TAG = "RegPC"
REG_A_TAG = "RegA"
REG_X_TAG = "RegX"
REG_Y_TAG = "RegY"
REG_S_TAG = "RegS"
STATUS_N_TAG = "StatusN"
STATUS_V_TAG = "StatusV"
STATUS_B_TAG = "StatusB"
STATUS_D_TAG = "StatusD"
STATUS_I_TAG = "StatusI"
STATUS_Z_TAG = "StatusZ"
STATUS_C_TAG = "StatusC"
REG_OPCODE_TAG = "RegOpcode"
REG_OPCODE_ADDR_TAG = "RegOpcodeAddr"
REG_OPCODE_DISASM_TAG = "RegOpcodeDisasm"

# Other tags
SIM_ERROR_TEXT_TAG = "SimErrorText"
MEM_PAGE_INPUT_TAG = "MemPageInput"
MEM_PAGE_RANGE_TAG = "MemPageRange"
MEM_MONITOR_TAG = "MemMonitor"


def _build_opcode_disasm() -> dict[int, str]:
    disasm: dict[int, str] = {}
    for mnemonic, encodings in INSTRUCTION_MAP_6502.items():
        for i, opcode in enumerate(encodings):
            if opcode is not None:
                disasm[opcode] = f"{mnemonic} {ADDRESSING_MODES[i]}"
    return disasm


class DebugWindow:
    WINDOW_WIDTH = 480

    def __init__(self, app: Py6502App) -> None:
        self._app = app
        self._opcode_disasm = _build_opcode_disasm()
        self._mem_monitor_page = 0x00

    def build(self) -> None:
        disabled_theme = self._app.themes.disabled_button
        with dpg.window(
            label="Debug",
            width=self.WINDOW_WIDTH,
            height=VideoWindow.TEXTURE_HEIGHT * 3 + 40,
            no_close=True,
            pos=(VideoWindow.TEXTURE_WIDTH * 3 + 24, 20),
            tag=WINDOW_TAG,
        ):
            # --- Controls ---
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Play", tag=PLAY_BUTTON_TAG,
                    callback=self._play_handler, enabled=False,
                )
                dpg.add_button(
                    label="Pause", tag=PAUSE_BUTTON_TAG,
                    callback=self._pause_handler, enabled=True,
                )
                dpg.add_button(
                    label="Step", tag=INST_STEP_BUTTON_TAG,
                    callback=self._inst_step_handler, enabled=False,
                )
                dpg.add_button(
                    label="Cycle", tag=CYCLE_STEP_BUTTON_TAG,
                    callback=self._cycle_step_handler, enabled=False,
                )
                dpg.add_button(
                    label="Reset", tag=RESET_BUTTON_TAG,
                    callback=self._reset_handler,
                )
            # Apply disabled theme to all control buttons
            for tag in (PLAY_BUTTON_TAG, PAUSE_BUTTON_TAG, INST_STEP_BUTTON_TAG,
                        CYCLE_STEP_BUTTON_TAG, RESET_BUTTON_TAG):
                dpg.bind_item_theme(tag, disabled_theme)

            dpg.add_separator()

            # --- CPU Registers ---
            dpg.add_text("CPU Registers", color=(255, 255, 0))
            with dpg.group(horizontal=True):
                dpg.add_text("PC:"); dpg.add_text("0000", tag=REG_PC_TAG)
                dpg.add_text("  A:"); dpg.add_text("00", tag=REG_A_TAG)
                dpg.add_text("  X:"); dpg.add_text("00", tag=REG_X_TAG)
                dpg.add_text("  Y:"); dpg.add_text("00", tag=REG_Y_TAG)
                dpg.add_text("  S:"); dpg.add_text("00", tag=REG_S_TAG)
            with dpg.group(horizontal=True):
                dpg.add_text("Status:")
                dpg.add_text("N:0", tag=STATUS_N_TAG)
                dpg.add_text("V:0", tag=STATUS_V_TAG)
                dpg.add_text("B:0", tag=STATUS_B_TAG)
                dpg.add_text("D:0", tag=STATUS_D_TAG)
                dpg.add_text("I:0", tag=STATUS_I_TAG)
                dpg.add_text("Z:0", tag=STATUS_Z_TAG)
                dpg.add_text("C:0", tag=STATUS_C_TAG)
            with dpg.group(horizontal=True):
                dpg.add_text("Opcode:")
                dpg.add_text("00", tag=REG_OPCODE_TAG)
                dpg.add_text("@")
                dpg.add_text("0000", tag=REG_OPCODE_ADDR_TAG)
            with dpg.group(horizontal=True):
                dpg.add_text("Decode:")
                dpg.add_text("", tag=REG_OPCODE_DISASM_TAG)

            dpg.add_text("", tag=SIM_ERROR_TEXT_TAG, color=(255, 0, 0), show=False)

            dpg.add_separator()

            # --- Memory Monitor ---
            dpg.add_text("Memory Monitor", color=(255, 255, 0))
            with dpg.group(horizontal=True, horizontal_spacing=0):
                dpg.add_text("Page: 0x")
                dpg.add_input_text(
                    tag=MEM_PAGE_INPUT_TAG,
                    default_value="00",
                    width=32,
                    callback=self._on_mem_page_changed,
                    uppercase=True,
                    hexadecimal=True,
                    no_spaces=True,
                )
                dpg.add_text(
                    " (0x0000 ~ 0x00FF)", tag=MEM_PAGE_RANGE_TAG,
                )
            dpg.add_text("", tag=MEM_MONITOR_TAG)

    def refresh(self, system: System) -> None:
        self._update_registers(system)
        self._update_memory_monitor(system)

    def on_sim_state_changed(self, *, running: bool, error: str | None = None) -> None:
        if error is not None:
            dpg.configure_item(PLAY_BUTTON_TAG, enabled=False)
            dpg.configure_item(PAUSE_BUTTON_TAG, enabled=False)
            dpg.configure_item(INST_STEP_BUTTON_TAG, enabled=False)
            dpg.configure_item(CYCLE_STEP_BUTTON_TAG, enabled=False)
            dpg.set_value(SIM_ERROR_TEXT_TAG, f"ERROR: {error}")
            dpg.configure_item(SIM_ERROR_TEXT_TAG, show=True)
        elif running:
            dpg.configure_item(PLAY_BUTTON_TAG, enabled=False)
            dpg.configure_item(PAUSE_BUTTON_TAG, enabled=True)
            dpg.configure_item(INST_STEP_BUTTON_TAG, enabled=False)
            dpg.configure_item(CYCLE_STEP_BUTTON_TAG, enabled=False)
        else:
            dpg.configure_item(PLAY_BUTTON_TAG, enabled=True)
            dpg.configure_item(PAUSE_BUTTON_TAG, enabled=False)
            dpg.configure_item(INST_STEP_BUTTON_TAG, enabled=True)
            dpg.configure_item(CYCLE_STEP_BUTTON_TAG, enabled=True)

    def on_reset(self) -> None:
        dpg.configure_item(SIM_ERROR_TEXT_TAG, show=False)
        dpg.configure_item(PLAY_BUTTON_TAG, enabled=True)
        dpg.configure_item(PAUSE_BUTTON_TAG, enabled=True)
        dpg.configure_item(INST_STEP_BUTTON_TAG, enabled=False)
        dpg.configure_item(CYCLE_STEP_BUTTON_TAG, enabled=False)

    # ------------------------------------------------------------------
    # Register and memory display
    # ------------------------------------------------------------------
    def _update_registers(self, system: System) -> None:
        regs = system.get_registers()
        dpg.set_value(REG_PC_TAG, f"{regs['PC']:04X}")
        dpg.set_value(REG_A_TAG, f"{regs['ACC']:02X}")
        dpg.set_value(REG_X_TAG, f"{regs['X']:02X}")
        dpg.set_value(REG_Y_TAG, f"{regs['Y']:02X}")
        dpg.set_value(REG_S_TAG, f"{regs['S']:02X}")
        p = regs["P"]
        dpg.set_value(STATUS_N_TAG, f"N:{(p >> 7) & 1}")
        dpg.set_value(STATUS_V_TAG, f"V:{(p >> 6) & 1}")
        dpg.set_value(STATUS_B_TAG, f"B:{(p >> 4) & 1}")
        dpg.set_value(STATUS_D_TAG, f"D:{(p >> 3) & 1}")
        dpg.set_value(STATUS_I_TAG, f"I:{(p >> 2) & 1}")
        dpg.set_value(STATUS_Z_TAG, f"Z:{(p >> 1) & 1}")
        dpg.set_value(STATUS_C_TAG, f"C:{p & 1}")
        opcode = regs["OPCODE"]
        dpg.set_value(REG_OPCODE_TAG, f"{opcode:02X}")
        dpg.set_value(REG_OPCODE_ADDR_TAG, f"{regs['OPCODE_ADDR']:04X}")
        dpg.set_value(REG_OPCODE_DISASM_TAG, self._opcode_disasm.get(opcode, "???"))

    def _update_memory_monitor(self, system: System) -> None:
        page = self._mem_monitor_page
        base = page << 8
        lines: list[str] = []
        if not system.is_mapped(base):
            dpg.set_value(MEM_MONITOR_TAG, f"{base:04X}: Unmapped memory range")
            dpg.configure_item(MEM_MONITOR_TAG, color=(255, 0, 0))
            return
        dpg.configure_item(MEM_MONITOR_TAG, color=(255, 255, 255))
        for row in range(0, 0x100, 16):
            addr = base + row
            row_bytes = [system.peek(addr + i) for i in range(16)]
            left = " ".join(f"{b:02X}" for b in row_bytes[:8])
            right = " ".join(f"{b:02X}" for b in row_bytes[8:])
            ascii_repr = "".join(
                chr(b) if 0x20 <= b <= 0x7E else "." for b in row_bytes
            )
            lines.append(f"{addr:04X}: {left}  {right}  |{ascii_repr}|")
        dpg.set_value(MEM_MONITOR_TAG, "\n".join(lines))

    def _on_mem_page_changed(self, sender: int, app_data: str, user_data: object) -> None:
        try:
            value = int(app_data, 16)
        except ValueError:
            dpg.set_value(MEM_PAGE_INPUT_TAG, f"{self._mem_monitor_page:02X}")
            return
        if not 0 <= value <= 0xFF:
            dpg.set_value(MEM_PAGE_INPUT_TAG, f"{self._mem_monitor_page:02X}")
            return
        self._mem_monitor_page = value
        dpg.set_value(MEM_PAGE_INPUT_TAG, f"{value:02X}")
        dpg.set_value(
            MEM_PAGE_RANGE_TAG, f" (0x{value:02X}00 ~ 0x{value:02X}FF)",
        )
        if self._app.system is not None:
            self._update_memory_monitor(self._app.system)

    # ------------------------------------------------------------------
    # Control callbacks
    # ------------------------------------------------------------------
    def _play_handler(self) -> None:
        self._app._play_handler()

    def _pause_handler(self) -> None:
        self._app._pause_handler()

    def _reset_handler(self) -> None:
        self._app._reset_handler()

    def _inst_step_handler(self) -> None:
        if self._app.system is None:
            return
        try:
            self._app.system.step_instruction()
        except (InvalidOPCode, UnallocatedAddressError) as exc:
            self._app._on_sim_error(exc)
            return
        self._app._video.update_framebuffer(self._app.system.get_framebuffer())
        self.refresh(self._app.system)

    def _cycle_step_handler(self) -> None:
        if self._app.system is None:
            return
        try:
            self._app.system.step_cycle()
        except (InvalidOPCode, UnallocatedAddressError) as exc:
            self._app._on_sim_error(exc)
            return
        self._app._video.update_framebuffer(self._app.system.get_framebuffer())
        self.refresh(self._app.system)
