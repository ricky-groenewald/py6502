"""Video output window — 256x240 framebuffer rendered at 3x magnification.

The texture is a DearPyGui **raw** texture bound to the sim's RGBA
buffer. The sim mutates that buffer in place from cdef code; the
raw-texture binding means DPG re-uploads from the same memory every
``render_dearpygui_frame()`` with no Python-level copies. On system
load/swap, ``bind_system_framebuffer`` rebinds the texture onto the
newly constructed display's buffer.
"""
from __future__ import annotations

from array import array
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
        # Startup placeholder buffer (shown before a System is loaded).
        # Held on the instance so it can't be GC'd while DPG holds a
        # raw-texture reference to it.
        self._placeholder: array = array(
            "f", [0.0] * (self.TEXTURE_WIDTH * self.TEXTURE_HEIGHT * 4)
        )
        # Whichever buffer the raw texture is currently bound to —
        # either the placeholder above, or the sim's own RGBA buffer
        # once bind_system_framebuffer is called. Kept referenced on
        # the window so it outlives every DPG read.
        self._bound_buffer: object = self._placeholder

    def build_texture_registry(self) -> None:
        with dpg.texture_registry(show=False):
            dpg.add_raw_texture(
                self.TEXTURE_WIDTH, self.TEXTURE_HEIGHT, self._placeholder,
                tag=self.TEXTURE_TAG,
                format=dpg.mvFormat_Float_rgba,
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

    def bind_system_framebuffer(self, framebuffer: object) -> None:
        """Rebind the raw texture onto a sim-owned buffer.

        Called from ``Py6502App._wire_system`` whenever the active
        System changes (preset load, user-selected YAML, reset to a
        different config). ``framebuffer`` must be the buffer returned
        by ``System.get_framebuffer()`` — an ``array.array('f')`` of
        exactly ``TEXTURE_WIDTH * TEXTURE_HEIGHT * 4`` floats, owned
        by the sim's display peripheral.

        If the sim has no display (``get_framebuffer()`` returns
        ``None``) we rebind onto the zeroed placeholder instead so the
        texture never dangles.
        """
        if framebuffer is None:
            framebuffer = self._placeholder
        self._bound_buffer = framebuffer
        dpg.set_value(self.TEXTURE_TAG, framebuffer)

    def is_focused(self) -> bool:
        return dpg.get_item_state(self.VIDEO_WINDOW_TAG).get("focused", False)
