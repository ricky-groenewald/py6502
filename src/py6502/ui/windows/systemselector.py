"""System selector modal — choose a preset or user YAML to boot."""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from py6502.ui.utils.presets import discover_presets, load_user_config_metadata
from py6502.ui.utils.settings import save_settings

if TYPE_CHECKING:
    from py6502.ui.app import Py6502App

WINDOW_TAG = "SystemSelectorWindow"
PRESET_GROUP_TAG = "SystemSelectorPresetGroup"
USER_GROUP_TAG = "SystemSelectorUserGroup"
FILE_DIALOG_TAG = "SystemSelectorFileDialog"
SELECTED_TAG = "SystemSelectorSelected"


class SystemSelectorWindow:
    def __init__(self, app: Py6502App) -> None:
        self._app = app
        self._entries: list[dict] = []
        self._selected_path: str | None = None

    def build(self) -> None:
        with dpg.window(
            label="Select System",
            width=500,
            height=400,
            show=False,
            modal=True,
            no_resize=True,
            tag=WINDOW_TAG,
        ):
            dpg.add_text("Presets", color=(255, 255, 0))
            dpg.add_group(tag=PRESET_GROUP_TAG)

            dpg.add_separator()
            dpg.add_text("User Configs", color=(255, 255, 0))
            dpg.add_group(tag=USER_GROUP_TAG)
            dpg.add_button(label="Load from file...", callback=self._on_browse)

            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label="Launch", callback=self._on_launch)
                dpg.add_button(label="Cancel", callback=self._on_cancel)

        # File dialog for user YAML configs
        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self._on_file_selected,
            tag=FILE_DIALOG_TAG,
            width=700,
            height=400,
        ):
            dpg.add_file_extension(".yaml", color=(0, 255, 0, 255))
            dpg.add_file_extension(".yml", color=(0, 255, 0, 255))

    def show(self) -> None:
        self._refresh_entries()
        dpg.show_item(WINDOW_TAG)

    # ------------------------------------------------------------------
    # Entry list management
    # ------------------------------------------------------------------
    def _refresh_entries(self) -> None:
        self._entries.clear()
        self._selected_path = None

        # Clear existing children
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
        # Clean up stale paths
        self._app.settings.user_config_paths = valid_paths

        # Auto-select first entry
        if self._entries:
            self._selected_path = self._entries[0]["path"]

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
                    label="X",
                    width=40,
                    callback=lambda s, a, u: self._on_remove_user_config(u),
                    user_data=path,
                )

    def _on_select(self, path: str) -> None:
        self._selected_path = path

    def _on_remove_user_config(self, path: str) -> None:
        if path in self._app.settings.user_config_paths:
            self._app.settings.user_config_paths.remove(path)
            save_settings(self._app.settings)
            self._refresh_entries()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_launch(self) -> None:
        if self._selected_path is None:
            return
        dpg.hide_item(WINDOW_TAG)
        self._app._load_system(self._selected_path)

    def _on_cancel(self) -> None:
        dpg.hide_item(WINDOW_TAG)

    def _on_browse(self) -> None:
        dpg.show_item(FILE_DIALOG_TAG)

    def _on_file_selected(self, sender: int, app_data: dict, user_data: object) -> None:
        file_path = app_data.get("file_path_name", "")
        if not file_path:
            return
        # Add to user config list if not already present
        if file_path not in self._app.settings.user_config_paths:
            self._app.settings.user_config_paths.append(file_path)
            save_settings(self._app.settings)
        self._refresh_entries()
        self._selected_path = file_path
