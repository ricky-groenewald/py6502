"""Video output window — 256x240 framebuffer rendered at 3x magnification."""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

if TYPE_CHECKING:
    from py6502.ui.app import Py6502App


class VideoWindow:
    TEXTURE_WIDTH = 256
    TEXTURE_HEIGHT = 240
    TEXTURE_TAG = "OutputTexture"
    VIDEO_WINDOW_TAG = "VideoOutputWindow"

    def __init__(self, app: Py6502App) -> None:
        self._app = app

    def build_texture_registry(self) -> None:
        initial = [0.0] * (self.TEXTURE_WIDTH * self.TEXTURE_HEIGHT * 4)
        with dpg.texture_registry(show=False):
            dpg.add_dynamic_texture(
                self.TEXTURE_WIDTH, self.TEXTURE_HEIGHT, initial,
                tag=self.TEXTURE_TAG,
            )

    def build(self) -> None:
        with dpg.window(
            label="Video Output",
            width=self.TEXTURE_WIDTH * 3 + 16,
            height=self.TEXTURE_HEIGHT * 3 + 16,
            no_resize=True,
            no_close=True,
            no_title_bar=True,
            tag=self.VIDEO_WINDOW_TAG,
        ):
            dpg.draw_image(
                self.TEXTURE_TAG,
                (0, 20),
                (self.TEXTURE_WIDTH * 3, self.TEXTURE_HEIGHT * 3 + 1),
            )

    def update_framebuffer(self, framebuffer: object) -> None:
        dpg.set_value(self.TEXTURE_TAG, framebuffer)

    def is_focused(self) -> bool:
        return dpg.get_item_state(self.VIDEO_WINDOW_TAG).get("focused", False)
