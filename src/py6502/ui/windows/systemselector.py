"""System selector modal — choose a preset, user YAML, or build a custom system."""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from py6502.sim.system.config import (
    ComponentSpec,
    CpuSpec,
    MemoryRegion,
    SystemConfig,
)
from py6502.sim.system import System
from py6502.ui.utils.presets import discover_presets, load_user_config_metadata
from py6502.ui.utils.settings import save_settings

if TYPE_CHECKING:
    from py6502.ui.app import Py6502App

WINDOW_TAG = "SystemSelectorWindow"
LEFT_PANE_TAG = "SystemSelectorLeftPane"
PRESET_GROUP_TAG = "SystemSelectorPresetGroup"
USER_GROUP_TAG = "SystemSelectorUserGroup"
RIGHT_PANE_TAG = "SystemSelectorRightPane"
FILE_DIALOG_TAG = "SystemSelectorFileDialog"

# Custom system builder tags
CUSTOM_NAME_TAG = "CustomSystemName"
CUSTOM_CPU_HZ_TAG = "CustomSystemCpuHz"
CUSTOM_RAM_START_TAG = "CustomSystemRamStart"
CUSTOM_RAM_SIZE_TAG = "CustomSystemRamSize"
CUSTOM_ROM_START_TAG = "CustomSystemRomStart"
CUSTOM_ROM_SIZE_TAG = "CustomSystemRomSize"
CUSTOM_ROM_FILE_TAG = "CustomSystemRomFile"
CUSTOM_ROM_FILE_DIALOG_TAG = "CustomSystemRomFileDialog"
CUSTOM_DISPLAY_TAG = "CustomSystemDisplay"
CUSTOM_DISPLAY_ADDR_TAG = "CustomSystemDisplayAddr"
CUSTOM_INPUT_TAG = "CustomSystemInput"
CUSTOM_INPUT_ADDR_TAG = "CustomSystemInputAddr"
CUSTOM_STATUS_TAG = "CustomSystemStatus"

# Info pane tags
INFO_PANE_TAG = "SystemSelectorInfoPane"

# Selection state
CUSTOM_SYSTEM_ID = "__custom__"


class SystemSelectorWindow:
    def __init__(self, app: Py6502App) -> None:
        self._app = app
        self._entries: list[dict] = []
        self._selected_path: str | None = None
        self._selected_is_custom = False
        self._custom_rom_path: str = ""

    def build(self) -> None:
        with dpg.window(
            label="New System",
            width=820,
            height=520,
            show=False,
            modal=True,
            no_resize=True,
            tag=WINDOW_TAG,
        ):
            with dpg.group(horizontal=True):
                # --- Left pane: system list ---
                with dpg.child_window(width=300, height=440, tag=LEFT_PANE_TAG):
                    dpg.add_text("Presets", color=(255, 255, 0))
                    dpg.add_group(tag=PRESET_GROUP_TAG)

                    dpg.add_separator()
                    dpg.add_text("User Configs", color=(255, 255, 0))
                    dpg.add_group(tag=USER_GROUP_TAG)
                    dpg.add_button(label="Load from file...", callback=self._on_browse)

                    dpg.add_separator()
                    dpg.add_text("Custom", color=(255, 255, 0))
                    self._build_custom_card()

                # --- Right pane: info / config ---
                with dpg.child_window(width=-1, height=440, tag=RIGHT_PANE_TAG):
                    # Info pane (shown for presets/user configs)
                    with dpg.group(tag=INFO_PANE_TAG, show=True):
                        dpg.add_text("Select a system from the left panel.")

                    # Custom system builder (hidden by default)
                    self._build_custom_form()

            # --- Bottom buttons ---
            with dpg.group(horizontal=True):
                dpg.add_button(label="Launch", width=120, callback=self._on_launch)
                dpg.add_button(label="Cancel", width=120, callback=self._on_cancel)

        # File dialogs
        with dpg.file_dialog(
            directory_selector=False, show=False,
            callback=self._on_file_selected, tag=FILE_DIALOG_TAG,
            width=700, height=400,
        ):
            dpg.add_file_extension(".yaml", color=(0, 255, 0, 255))
            dpg.add_file_extension(".yml", color=(0, 255, 0, 255))

        with dpg.file_dialog(
            directory_selector=False, show=False,
            callback=self._on_rom_file_selected, tag=CUSTOM_ROM_FILE_DIALOG_TAG,
            width=700, height=400,
        ):
            dpg.add_file_extension(".bin", color=(0, 255, 0, 255))
            dpg.add_file_extension(".rom", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def _build_custom_card(self) -> None:
        card_theme = self._app.themes.card_button
        btn = dpg.add_button(
            label="Custom 6502 System\n  Build a system from scratch",
            width=-1,
            callback=lambda: self._on_select_custom(),
            parent=LEFT_PANE_TAG,
        )
        dpg.bind_item_theme(btn, card_theme)

    def _build_custom_form(self) -> None:
        with dpg.group(tag="CustomSystemForm", parent=RIGHT_PANE_TAG, show=False):
            dpg.add_text("Custom System Configuration", color=(255, 255, 0))
            dpg.add_separator()

            dpg.add_text("System Name:")
            dpg.add_input_text(
                tag=CUSTOM_NAME_TAG, default_value="My System", width=300,
            )

            dpg.add_spacer(height=4)
            dpg.add_text("CPU Frequency (Hz):")
            dpg.add_input_int(
                tag=CUSTOM_CPU_HZ_TAG, default_value=1000000,
                min_value=1, min_clamped=True, width=200,
            )

            dpg.add_spacer(height=4)
            dpg.add_text("RAM", color=(200, 200, 100))
            with dpg.group(horizontal=True):
                dpg.add_text("Start: 0x")
                dpg.add_input_text(
                    tag=CUSTOM_RAM_START_TAG, default_value="0000",
                    width=50, uppercase=True, hexadecimal=True, no_spaces=True,
                )
                dpg.add_text("  Size: 0x")
                dpg.add_input_text(
                    tag=CUSTOM_RAM_SIZE_TAG, default_value="8000",
                    width=50, uppercase=True, hexadecimal=True, no_spaces=True,
                )

            dpg.add_spacer(height=4)
            dpg.add_text("ROM", color=(200, 200, 100))
            with dpg.group(horizontal=True):
                dpg.add_text("Start: 0x")
                dpg.add_input_text(
                    tag=CUSTOM_ROM_START_TAG, default_value="8000",
                    width=50, uppercase=True, hexadecimal=True, no_spaces=True,
                )
                dpg.add_text("  Size: 0x")
                dpg.add_input_text(
                    tag=CUSTOM_ROM_SIZE_TAG, default_value="8000",
                    width=50, uppercase=True, hexadecimal=True, no_spaces=True,
                )
            with dpg.group(horizontal=True):
                dpg.add_text("Binary:")
                dpg.add_input_text(
                    tag=CUSTOM_ROM_FILE_TAG, readonly=True, width=280,
                    hint="(optional)",
                )
                dpg.add_button(
                    label="Browse...",
                    callback=lambda: dpg.show_item(CUSTOM_ROM_FILE_DIALOG_TAG),
                )

            dpg.add_spacer(height=4)
            dpg.add_text("Peripherals", color=(200, 200, 100))
            with dpg.group(horizontal=True):
                dpg.add_text("Display:")
                dpg.add_combo(
                    tag=CUSTOM_DISPLAY_TAG,
                    items=["None", "Apple1Display"],
                    default_value="Apple1Display", width=160,
                )
                dpg.add_text(" @ 0x")
                dpg.add_input_text(
                    tag=CUSTOM_DISPLAY_ADDR_TAG, default_value="D012",
                    width=50, uppercase=True, hexadecimal=True, no_spaces=True,
                )
            with dpg.group(horizontal=True):
                dpg.add_text("Input:  ")
                dpg.add_combo(
                    tag=CUSTOM_INPUT_TAG,
                    items=["None", "Apple1Keyboard"],
                    default_value="Apple1Keyboard", width=160,
                )
                dpg.add_text(" @ 0x")
                dpg.add_input_text(
                    tag=CUSTOM_INPUT_ADDR_TAG, default_value="D010",
                    width=50, uppercase=True, hexadecimal=True, no_spaces=True,
                )

            dpg.add_spacer(height=8)
            dpg.add_text("", tag=CUSTOM_STATUS_TAG)

    def show(self) -> None:
        self._refresh_entries()
        dpg.show_item(WINDOW_TAG)

    # ------------------------------------------------------------------
    # Entry list management
    # ------------------------------------------------------------------
    def _refresh_entries(self) -> None:
        self._entries.clear()
        self._selected_path = None
        self._selected_is_custom = False

        for tag in (PRESET_GROUP_TAG, USER_GROUP_TAG):
            dpg.delete_item(tag, children_only=True)

        # Presets
        for meta in discover_presets():
            self._entries.append(meta)
            self._add_entry_row(meta, PRESET_GROUP_TAG, removable=False)

        # User configs
        valid_paths: list[str] = []
        for path in self._app.settings.user_config_paths:
            meta = load_user_config_metadata(path)
            if meta is not None:
                self._entries.append(meta)
                self._add_entry_row(meta, USER_GROUP_TAG, removable=True)
                valid_paths.append(path)
        self._app.settings.user_config_paths = valid_paths

        # Auto-select first entry
        if self._entries:
            self._on_select(self._entries[0]["path"])

    def _add_entry_row(self, meta: dict, parent_tag: str, *, removable: bool) -> None:
        card_theme = self._app.themes.card_button
        path = meta["path"]
        label = meta["name"]
        if meta["description"]:
            label += f"\n  {meta['description'].strip().splitlines()[0]}"

        with dpg.group(horizontal=True, parent=parent_tag):
            btn = dpg.add_button(
                label=label,
                width=-60 if removable else -1,
                callback=lambda s, a, u: self._on_select(u),
                user_data=path,
            )
            dpg.bind_item_theme(btn, card_theme)
            if removable:
                dpg.add_button(
                    label="X", width=40,
                    callback=lambda s, a, u: self._on_remove_user_config(u),
                    user_data=path,
                )

    def _on_select(self, path: str) -> None:
        self._selected_path = path
        self._selected_is_custom = False
        # Show info pane, hide custom form
        dpg.configure_item(INFO_PANE_TAG, show=True)
        dpg.configure_item("CustomSystemForm", show=False)
        # Update info pane with selected system metadata
        dpg.delete_item(INFO_PANE_TAG, children_only=True)
        meta = next((e for e in self._entries if e["path"] == path), None)
        if meta:
            dpg.add_text(meta["name"], parent=INFO_PANE_TAG, color=(100, 200, 255))
            dpg.add_separator(parent=INFO_PANE_TAG)
            if meta["description"]:
                dpg.add_text(meta["description"].strip(), parent=INFO_PANE_TAG, wrap=460)
            if meta["author"]:
                dpg.add_spacer(parent=INFO_PANE_TAG, height=8)
                dpg.add_text(
                    f"Author: {meta['author']}", parent=INFO_PANE_TAG,
                    color=(180, 180, 180),
                )
            if meta["tags"]:
                tags_str = ", ".join(str(t) for t in meta["tags"])
                dpg.add_text(
                    f"Tags: {tags_str}", parent=INFO_PANE_TAG,
                    color=(180, 180, 180),
                )

    def _on_select_custom(self) -> None:
        self._selected_path = None
        self._selected_is_custom = True
        dpg.configure_item(INFO_PANE_TAG, show=False)
        dpg.configure_item("CustomSystemForm", show=True)
        dpg.set_value(CUSTOM_STATUS_TAG, "")

    def _on_remove_user_config(self, path: str) -> None:
        if path in self._app.settings.user_config_paths:
            self._app.settings.user_config_paths.remove(path)
            save_settings(self._app.settings)
            self._refresh_entries()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_launch(self) -> None:
        if self._selected_is_custom:
            self._launch_custom()
        elif self._selected_path is not None:
            dpg.hide_item(WINDOW_TAG)
            self._app._load_system(self._selected_path)
        else:
            return

    def _launch_custom(self) -> None:
        """Build a SystemConfig from the custom form and launch it."""
        try:
            name = dpg.get_value(CUSTOM_NAME_TAG) or "Custom System"
            cpu_hz = dpg.get_value(CUSTOM_CPU_HZ_TAG)
            ram_start = int(dpg.get_value(CUSTOM_RAM_START_TAG), 16)
            ram_size = int(dpg.get_value(CUSTOM_RAM_SIZE_TAG), 16)
            rom_start = int(dpg.get_value(CUSTOM_ROM_START_TAG), 16)
            rom_size = int(dpg.get_value(CUSTOM_ROM_SIZE_TAG), 16)
        except ValueError:
            self._set_custom_status("Invalid hex value in address or size fields", error=True)
            return

        if ram_size == 0 and rom_size == 0:
            self._set_custom_status("At least one memory region is required", error=True)
            return

        # Build memory regions
        memory = []
        if ram_size > 0:
            memory.append(MemoryRegion(name="RAM", start=ram_start, size=ram_size))
        if rom_size > 0:
            source = None
            if self._custom_rom_path:
                source = f"file:{self._custom_rom_path}"
            memory.append(MemoryRegion(
                name="ROM", start=rom_start, size=rom_size,
                read_only=True, source=source,
            ))

        # Build display
        display = None
        display_type = dpg.get_value(CUSTOM_DISPLAY_TAG)
        if display_type != "None":
            try:
                display_addr = int(dpg.get_value(CUSTOM_DISPLAY_ADDR_TAG), 16)
            except ValueError:
                self._set_custom_status("Invalid display address", error=True)
                return
            display = ComponentSpec(type=display_type, address=display_addr)

        # Build inputs
        inputs = []
        input_type = dpg.get_value(CUSTOM_INPUT_TAG)
        if input_type != "None":
            try:
                input_addr = int(dpg.get_value(CUSTOM_INPUT_ADDR_TAG), 16)
            except ValueError:
                self._set_custom_status("Invalid input address", error=True)
                return
            inputs.append(ComponentSpec(type=input_type, address=input_addr))

        config = SystemConfig(
            version=1,
            id="custom",
            name=name,
            description="Custom system configuration",
            cpu=CpuSpec(type="MOS6502", hz=cpu_hz),
            memory=tuple(memory),
            display=display,
            inputs=tuple(inputs),
        )

        try:
            system = System(config)
        except Exception as exc:
            self._set_custom_status(str(exc), error=True)
            return

        dpg.hide_item(WINDOW_TAG)
        self._app._load_system_from_instance(system, name)

    def _set_custom_status(self, text: str, *, error: bool = False) -> None:
        dpg.set_value(CUSTOM_STATUS_TAG, text)
        color = (255, 80, 80) if error else (80, 255, 80)
        dpg.configure_item(CUSTOM_STATUS_TAG, color=color)

    def _on_cancel(self) -> None:
        dpg.hide_item(WINDOW_TAG)

    def _on_browse(self) -> None:
        dpg.show_item(FILE_DIALOG_TAG)

    def _on_file_selected(self, sender: int, app_data: dict, user_data: object) -> None:
        file_path = app_data.get("file_path_name", "")
        if not file_path:
            return
        if file_path not in self._app.settings.user_config_paths:
            self._app.settings.user_config_paths.append(file_path)
            save_settings(self._app.settings)
        self._refresh_entries()
        self._on_select(file_path)

    def _on_rom_file_selected(self, sender: int, app_data: dict, user_data: object) -> None:
        file_path = app_data.get("file_path_name", "")
        if file_path:
            self._custom_rom_path = file_path
            dpg.set_value(CUSTOM_ROM_FILE_TAG, file_path)
