"""Custom About dialog — project-specific information for py6502."""
from __future__ import annotations

from importlib import metadata

import dearpygui.dearpygui as dpg

WINDOW_TAG = "AboutWindow"


class AboutWindow:
    def build(self) -> None:
        # Gather version info
        try:
            version = metadata.version("py6502")
        except metadata.PackageNotFoundError:
            version = "dev"
        try:
            dpg_version = metadata.version("dearpygui")
        except metadata.PackageNotFoundError:
            dpg_version = "unknown"

        with dpg.window(
            label="About py6502",
            width=440,
            height=300,
            show=False,
            modal=True,
            no_resize=True,
            tag=WINDOW_TAG,
        ):
            dpg.add_text("py6502", color=(100, 200, 255))
            dpg.add_text("Emulator of everything 6502")
            dpg.add_separator()

            dpg.add_text(f"Version: {version}")
            dpg.add_text("Author: Ricky Groenewald")
            dpg.add_spacer(height=4)
            dpg.add_text(
                "A cycle-accurate 6502 simulator with a DearPyGui frontend,\n"
                "aimed at hobbyists, educators, and retro-computing\n"
                "enthusiasts."
            )
            dpg.add_spacer(height=4)
            dpg.add_text(
                "License: Free for personal, educational, and hobbyist use.\n"
                "Commercial use is not permitted."
            )
            dpg.add_separator()

            dpg.add_text(
                "Uses a custom DearPyGui build with LinearFiltering\n"
                "disabled (GL_NEAREST) for pixel-accurate rendering.",
                color=(180, 180, 180),
            )
            dpg.add_text(f"DearPyGui version: {dpg_version}", color=(180, 180, 180))

            dpg.add_separator()
            dpg.add_button(label="Close", callback=lambda: dpg.hide_item(WINDOW_TAG))

    def show(self) -> None:
        dpg.show_item(WINDOW_TAG)
