"""Keyboard input handler — translates DearPyGui key events to Apple I ASCII."""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

if TYPE_CHECKING:
    from py6502.ui.windows.video import VideoWindow


class KeyHandler:
    def __init__(self, video_window: VideoWindow, key_buffer: list[int]) -> None:
        self._video = video_window
        self._key_buffer = key_buffer

    def build(self) -> None:
        with dpg.handler_registry():
            dpg.add_key_press_handler(
                key=dpg.mvKey_None, callback=self._on_key_press,
            )

    def _on_key_press(self, sender: int, app_data: int, user_data: object) -> None:
        if not self._video.is_focused():
            return

        shift_down = (
            dpg.is_key_down(dpg.mvKey_LShift)
            or dpg.is_key_down(dpg.mvKey_RShift)
        )

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
    """Translate a DearPyGui key code into Apple I ASCII. Returns None for
    keys that have no mapping.

    The bare integer constants (601, 596, 602, 606) are platform key
    codes for ``;`` ``'`` ``=`` ``\\``` respectively that DearPyGui
    surfaces in callbacks but does not expose as named ``mvKey_*``
    enums. They were determined empirically by printing app_data on a
    macOS host; if a future DearPyGui release adds named constants,
    swap them in.
    """
    if dpg.mvKey_A <= app_data <= dpg.mvKey_Z:
        return chr(app_data - dpg.mvKey_A + ord("A"))
    if dpg.mvKey_0 <= app_data <= dpg.mvKey_9:
        if shift_down:
            return ")!@#$%^&*("[app_data - dpg.mvKey_0]
        return chr(app_data - dpg.mvKey_0 + ord("0"))
    if app_data == dpg.mvKey_Spacebar:
        return " "
    if app_data == dpg.mvKey_Comma:
        return "<" if shift_down else ","
    if app_data == dpg.mvKey_Period:
        return ">" if shift_down else "."
    if app_data == dpg.mvKey_Slash:
        return "?" if shift_down else "/"
    if app_data == 601:  # ; / :
        return ":" if shift_down else ";"
    if app_data == 596:  # ' / "
        return '"' if shift_down else "'"
    if app_data == dpg.mvKey_Open_Brace:
        return "{" if shift_down else "["
    if app_data == dpg.mvKey_Close_Brace:
        return "}" if shift_down else "]"
    if app_data == dpg.mvKey_Backslash:
        return "|" if shift_down else "\\"
    if app_data == dpg.mvKey_Minus:
        return "_" if shift_down else "-"
    if app_data == 602:  # = / +
        return "+" if shift_down else "="
    if app_data == 606:  # ` / ~
        return "~" if shift_down else "`"
    return None
