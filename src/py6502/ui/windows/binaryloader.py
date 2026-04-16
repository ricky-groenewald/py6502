"""Binary loader dialog — load a .bin/.rom file at an absolute address."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

if TYPE_CHECKING:
    from py6502.ui.app import Py6502App

WINDOW_TAG = "BinaryLoaderWindow"
FILE_PATH_TAG = "BinaryLoaderFilePath"
ADDRESS_TAG = "BinaryLoaderAddress"
STATUS_TAG = "BinaryLoaderStatus"
FILE_DIALOG_TAG = "BinaryLoaderFileDialog"


class BinaryLoaderWindow:
    def __init__(self, app: Py6502App) -> None:
        self._app = app
        self._file_path: str = ""

    def build(self) -> None:
        with dpg.window(
            label="Load Binary",
            width=500,
            height=180,
            show=False,
            tag=WINDOW_TAG,
        ):
            # File selection row
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag=FILE_PATH_TAG,
                    readonly=True,
                    width=380,
                    hint="No file selected",
                )
                dpg.add_button(label="Browse...", callback=self._on_browse)

            # Address row
            with dpg.group(horizontal=True):
                dpg.add_text("Address: 0x")
                dpg.add_input_text(
                    tag=ADDRESS_TAG,
                    default_value="0000",
                    width=60,
                    uppercase=True,
                    hexadecimal=True,
                    no_spaces=True,
                )

            # Action buttons
            with dpg.group(horizontal=True):
                dpg.add_button(label="Load", callback=self._on_load)
                dpg.add_button(label="Cancel", callback=self._on_cancel)

            # Status text
            dpg.add_text("", tag=STATUS_TAG)

        # File dialog
        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self._on_file_selected,
            tag=FILE_DIALOG_TAG,
            width=700,
            height=400,
        ):
            dpg.add_file_extension(".bin", color=(0, 255, 0, 255))
            dpg.add_file_extension(".rom", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def show(self) -> None:
        self._file_path = ""
        dpg.set_value(FILE_PATH_TAG, "")
        dpg.set_value(ADDRESS_TAG, "0000")
        dpg.set_value(STATUS_TAG, "")
        dpg.configure_item(STATUS_TAG, color=(255, 255, 255))
        dpg.show_item(WINDOW_TAG)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _on_browse(self) -> None:
        dpg.show_item(FILE_DIALOG_TAG)

    def _on_file_selected(self, sender: int, app_data: dict, user_data: object) -> None:
        file_path = app_data.get("file_path_name", "")
        if file_path:
            self._file_path = file_path
            dpg.set_value(FILE_PATH_TAG, file_path)

    def _on_load(self) -> None:
        if self._app.system is None:
            return

        if not self._file_path:
            self._set_status("No file selected", error=True)
            return

        address_str = dpg.get_value(ADDRESS_TAG)
        try:
            address = int(address_str, 16)
        except ValueError:
            self._set_status("Invalid address value", error=True)
            return

        try:
            data = Path(self._file_path).read_bytes()
            self._app.system.load_binary_at(address, data)
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return

        self._set_status(f"Loaded {len(data)} bytes at 0x{address:04X}")
        dpg.hide_item(WINDOW_TAG)

    def _on_cancel(self) -> None:
        dpg.hide_item(WINDOW_TAG)

    def _set_status(self, text: str, *, error: bool = False) -> None:
        dpg.set_value(STATUS_TAG, text)
        color = (255, 80, 80) if error else (80, 255, 80)
        dpg.configure_item(STATUS_TAG, color=color)
