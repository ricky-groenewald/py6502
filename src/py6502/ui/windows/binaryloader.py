"""Binary loader dialog — load a .bin/.rom file (or a bundled asset) at an absolute address."""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from py6502.sim.manifest import BinaryAsset
from py6502.ui.widgets import BinarySourcePicker

if TYPE_CHECKING:
    from py6502.ui.app import Py6502App

WINDOW_TAG = "BinaryLoaderWindow"
ADDRESS_TAG = "BinaryLoaderAddress"
STATUS_TAG = "BinaryLoaderStatus"
PICKER_PREFIX = "BinaryLoaderSource"


class BinaryLoaderWindow:
    def __init__(self, app: Py6502App) -> None:
        self._app = app
        self._picker = BinarySourcePicker(
            PICKER_PREFIX,
            path_width=300,
            combo_width=200,
            desc_wrap=420,
            on_asset_selected=self._on_asset_selected,
        )

    def build(self) -> None:
        with dpg.window(
            label="Load Binary",
            width=500,
            height=220,
            show=False,
            tag=WINDOW_TAG,
        ):
            self._picker.build()

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

            with dpg.group(horizontal=True):
                dpg.add_button(label="Load", callback=self._on_load)
                dpg.add_button(label="Cancel", callback=self._on_cancel)

            dpg.add_text("", tag=STATUS_TAG)

    def show(self) -> None:
        self._picker.reset()
        dpg.set_value(ADDRESS_TAG, "0000")
        dpg.set_value(STATUS_TAG, "")
        dpg.configure_item(STATUS_TAG, color=(255, 255, 255))
        dpg.show_item(WINDOW_TAG)

    def _on_asset_selected(self, asset: BinaryAsset) -> None:
        dpg.set_value(ADDRESS_TAG, f"{asset.default_address:04X}")

    def _on_load(self) -> None:
        if self._app.system is None:
            return

        if self._picker.is_empty():
            self._set_status("No binary selected", error=True)
            return

        try:
            address = int(dpg.get_value(ADDRESS_TAG), 16)
        except ValueError:
            self._set_status("Invalid address value", error=True)
            return

        try:
            data = self._picker.get_bytes()
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
