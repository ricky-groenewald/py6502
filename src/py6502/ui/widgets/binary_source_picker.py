"""Shared "binary source" picker — a file on disk or a bundled asset."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import dearpygui.dearpygui as dpg

from py6502.sim.manifest import BinaryAsset, list_binaries


def _format_size(n: int) -> str:
    return f"{n} B (0x{n:X})"


def _describe(asset: BinaryAsset) -> str:
    return f"Size: {_format_size(asset.size_bytes)}\n{asset.description}"


class BinarySourcePicker:
    """
    Renders a "From disk / Bundled" toggle plus the corresponding input
    widgets. Used by the runtime Load Binary dialog (one instance per
    window) and by the custom-system builder (one instance per binary
    row). Each instance owns a distinct tag prefix so multiple pickers
    coexist on the same screen.

    The picker returns a URI in the same shape as
    ``BinarySource.source`` — ``file:<abspath>`` or
    ``resource:<package>/<filename>`` — so the config-time and runtime
    binary-loading paths both accept it unchanged.
    """

    def __init__(
        self,
        tag_prefix: str,
        *,
        path_width: int = 260,
        combo_width: int = 180,
        desc_wrap: int = 500,
        on_asset_selected: Callable[[BinaryAsset], None] | None = None,
    ) -> None:
        self._prefix = tag_prefix
        self._path_width = path_width
        self._combo_width = combo_width
        self._desc_wrap = desc_wrap
        self._on_asset_selected = on_asset_selected

        self._assets: tuple[BinaryAsset, ...] = ()
        self._disk_path: str = ""
        self._selected_asset: BinaryAsset | None = None

    @property
    def _mode_tag(self) -> str:
        return f"{self._prefix}Mode"

    @property
    def _disk_group_tag(self) -> str:
        return f"{self._prefix}DiskGroup"

    @property
    def _bundled_group_tag(self) -> str:
        return f"{self._prefix}BundledGroup"

    @property
    def _path_tag(self) -> str:
        return f"{self._prefix}Path"

    @property
    def _combo_tag(self) -> str:
        return f"{self._prefix}Combo"

    @property
    def _desc_tag(self) -> str:
        return f"{self._prefix}Desc"

    @property
    def _dialog_tag(self) -> str:
        return f"{self._prefix}FileDialog"

    def build(self) -> None:
        """Render the picker into the current DPG container."""
        self._assets = list_binaries()
        if self._assets:
            self._selected_asset = self._assets[0]

        dpg.add_radio_button(
            tag=self._mode_tag,
            items=["From disk", "Bundled"],
            default_value="From disk",
            horizontal=True,
            callback=self._on_mode_changed,
        )

        with dpg.group(tag=self._disk_group_tag):
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag=self._path_tag,
                    readonly=True,
                    width=self._path_width,
                    hint="No file selected",
                )
                dpg.add_button(label="Browse...", callback=self._on_browse)

        with dpg.group(tag=self._bundled_group_tag, show=False):
            with dpg.group(horizontal=True):
                items = [a.name for a in self._assets]
                dpg.add_combo(
                    tag=self._combo_tag,
                    items=items,
                    default_value=items[0] if items else "",
                    width=self._combo_width,
                    callback=self._on_combo_changed,
                )
            dpg.add_text(
                _describe(self._assets[0]) if self._assets else "",
                tag=self._desc_tag,
                color=(180, 180, 180),
                wrap=self._desc_wrap,
            )

        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self._on_file_selected,
            tag=self._dialog_tag,
            width=700,
            height=400,
        ):
            dpg.add_file_extension(".bin", color=(0, 255, 0, 255))
            dpg.add_file_extension(".rom", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def destroy(self) -> None:
        """Delete the file dialog this picker owns. Call before the group
        containing the picker is itself deleted — DPG file dialogs are
        registered at the top level and would otherwise leak."""
        if dpg.does_item_exist(self._dialog_tag):
            dpg.delete_item(self._dialog_tag)

    def reset(self) -> None:
        """Clear any selection and reset the toggle to 'From disk'."""
        self._disk_path = ""
        if dpg.does_item_exist(self._path_tag):
            dpg.set_value(self._path_tag, "")
            dpg.set_value(self._mode_tag, "From disk")
            dpg.configure_item(self._disk_group_tag, show=True)
            dpg.configure_item(self._bundled_group_tag, show=False)
            if self._assets:
                self._selected_asset = self._assets[0]
                dpg.set_value(self._combo_tag, self._assets[0].name)
                dpg.set_value(self._desc_tag, _describe(self._assets[0]))

    def is_empty(self) -> bool:
        if dpg.get_value(self._mode_tag) == "From disk":
            return not self._disk_path
        return self._selected_asset is None

    def get_source(self) -> tuple[str, int | None]:
        """Return ``(uri, prefill_address_or_None)``. Raises ``ValueError``
        if nothing is selected."""
        if dpg.get_value(self._mode_tag) == "From disk":
            if not self._disk_path:
                raise ValueError("No file selected")
            return f"file:{self._disk_path}", None
        if self._selected_asset is None:
            raise ValueError("No bundled asset selected")
        return self._selected_asset.source, self._selected_asset.default_address

    def get_bytes(self) -> bytes:
        """Return the selected binary's raw bytes."""
        if dpg.get_value(self._mode_tag) == "From disk":
            if not self._disk_path:
                raise ValueError("No file selected")
            return Path(self._disk_path).read_bytes()
        if self._selected_asset is None:
            raise ValueError("No bundled asset selected")
        return self._selected_asset.data()

    def _on_mode_changed(self, sender: int, app_data: str, user_data: object) -> None:
        if app_data == "From disk":
            dpg.configure_item(self._disk_group_tag, show=True)
            dpg.configure_item(self._bundled_group_tag, show=False)
            return
        dpg.configure_item(self._disk_group_tag, show=False)
        dpg.configure_item(self._bundled_group_tag, show=True)
        if self._selected_asset is not None and self._on_asset_selected is not None:
            self._on_asset_selected(self._selected_asset)

    def _on_browse(self) -> None:
        dpg.show_item(self._dialog_tag)

    def _on_file_selected(self, sender: int, app_data: dict, user_data: object) -> None:
        path = app_data.get("file_path_name", "")
        if path:
            self._disk_path = path
            dpg.set_value(self._path_tag, path)

    def _on_combo_changed(self, sender: int, app_data: str, user_data: object) -> None:
        asset = next((a for a in self._assets if a.name == app_data), None)
        if asset is None:
            return
        self._selected_asset = asset
        dpg.set_value(self._desc_tag, _describe(asset))
        if self._on_asset_selected is not None:
            self._on_asset_selected(asset)
