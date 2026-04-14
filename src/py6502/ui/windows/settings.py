"""Settings window — app preferences for startup behavior and simulation."""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from py6502.ui.utils.settings import save_settings

if TYPE_CHECKING:
    from py6502.ui.app import Py6502App

WINDOW_TAG = "SettingsWindow"
STARTUP_LAST_SYSTEM_TAG = "SettingsStartupLastSystem"
HALT_INVALID_OPCODE_TAG = "SettingsHaltInvalidOpcode"
HALT_UNMAPPED_MEMORY_TAG = "SettingsHaltUnmappedMemory"


class SettingsWindow:
    def __init__(self, app: Py6502App) -> None:
        self._app = app

    def build(self) -> None:
        settings = self._app.settings
        with dpg.window(
            label="Settings",
            width=360,
            height=200,
            show=False,
            tag=WINDOW_TAG,
            on_close=self._on_close,
        ):
            dpg.add_text("Startup", color=(255, 255, 0))
            dpg.add_checkbox(
                label="Start with last used system",
                tag=STARTUP_LAST_SYSTEM_TAG,
                default_value=settings.startup_with_last_system,
                callback=self._on_startup_toggle,
            )

            dpg.add_separator()
            dpg.add_text("Simulation", color=(255, 255, 0))
            dpg.add_checkbox(
                label="Halt on invalid opcode",
                tag=HALT_INVALID_OPCODE_TAG,
                default_value=settings.halt_on_invalid_opcode,
                callback=self._on_halt_invalid_opcode_toggle,
            )
            dpg.add_checkbox(
                label="Halt on unmapped memory access",
                tag=HALT_UNMAPPED_MEMORY_TAG,
                default_value=settings.halt_on_unmapped_memory,
                callback=self._on_halt_unmapped_memory_toggle,
            )

    def show(self) -> None:
        dpg.show_item(WINDOW_TAG)
        dpg.focus_item(WINDOW_TAG)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _on_startup_toggle(self, sender: int, app_data: bool, user_data: object) -> None:
        self._app.settings.startup_with_last_system = app_data
        self._save()

    def _on_halt_invalid_opcode_toggle(self, sender: int, app_data: bool, user_data: object) -> None:
        self._app.settings.halt_on_invalid_opcode = app_data
        if self._app.system is not None:
            self._app.system.set_invalid_opcode_mode(1 if app_data else 0)
        self._save()

    def _on_halt_unmapped_memory_toggle(self, sender: int, app_data: bool, user_data: object) -> None:
        self._app.settings.halt_on_unmapped_memory = app_data
        if self._app.system is not None:
            self._app.system.set_unmapped_memory_mode(app_data)
        self._save()

    def _on_close(self) -> None:
        self._save()

    def _save(self) -> None:
        save_settings(self._app.settings)
