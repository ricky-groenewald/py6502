"""System selector modal — choose a preset, user YAML, or build a custom system."""
from __future__ import annotations

from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from py6502.sim.system import (
    ComponentSpec,
    CpuSpec,
    MemoryRegion,
    OptionSpec,
    System,
    SystemConfig,
)
from py6502.ui.utils.presets import discover_presets, load_user_config_metadata
from py6502.ui.utils.settings import save_settings

if TYPE_CHECKING:
    from py6502.ui.app import Py6502App

WINDOW_TAG = "SystemSelectorWindow"
LEFT_PANE_TAG = "SystemSelectorLeftPane"
PRESET_GROUP_TAG = "SystemSelectorPresetGroup"
USER_GROUP_TAG = "SystemSelectorUserGroup"
RIGHT_PANE_TAG = "SystemSelectorRightPane"
INFO_PANE_TAG = "SystemSelectorInfoPane"
FILE_DIALOG_TAG = "SystemSelectorFileDialog"

CUSTOM_FORM_TAG = "CustomSystemForm"
CUSTOM_NAME_TAG = "CustomSystemName"
CUSTOM_CPU_HZ_TAG = "CustomSystemCpuHz"
CUSTOM_REGIONS_TAG = "CustomSystemRegionsGroup"
CUSTOM_DISPLAY_TAG = "CustomSystemDisplay"
CUSTOM_DISPLAY_ADDR_TAG = "CustomSystemDisplayAddr"
CUSTOM_INPUT_TAG = "CustomSystemInput"
CUSTOM_INPUT_ADDR_TAG = "CustomSystemInputAddr"
CUSTOM_STATUS_TAG = "CustomSystemStatus"
SOURCE_FILE_DIALOG_TAG = "CustomSystemSourceFileDialog"


class SystemSelectorWindow:
    def __init__(self, app: Py6502App) -> None:
        self._app = app
        self._entries: list[dict] = []
        self._selected_path: str | None = None
        self._selected_is_custom = False
        self._region_counter = 0
        self._region_ids: list[int] = []
        self._source_dialog_target: int | None = None
        # Per-preset option selections, keyed by preset path. Persists across
        # re-selects so the user's picks stick if they navigate away and back.
        self._option_values: dict[str, dict[str, object]] = {}

    def build(self) -> None:
        with dpg.window(
            label="New System",
            width=820, height=520,
            show=False, no_resize=True,
            tag=WINDOW_TAG,
        ):
            with dpg.group(horizontal=True):
                with dpg.child_window(width=280, height=440, tag=LEFT_PANE_TAG):
                    dpg.add_text("Presets", color=(255, 255, 0))
                    dpg.add_group(tag=PRESET_GROUP_TAG)
                    dpg.add_separator()
                    dpg.add_text("User Configs", color=(255, 255, 0))
                    dpg.add_group(tag=USER_GROUP_TAG)
                    dpg.add_button(label="Load from file...", callback=self._on_browse)
                    dpg.add_separator()
                    dpg.add_text("Custom", color=(255, 255, 0))
                    self._build_custom_card()

                with dpg.child_window(width=-1, height=440, tag=RIGHT_PANE_TAG):
                    with dpg.group(tag=INFO_PANE_TAG, show=True):
                        dpg.add_text("Select a system from the left panel.")
                    self._build_custom_form()

            with dpg.group(horizontal=True):
                dpg.add_button(label="Launch", width=120, callback=self._on_launch)
                dpg.add_button(label="Cancel", width=120, callback=self._on_cancel)

        with dpg.file_dialog(
            directory_selector=False, show=False,
            callback=self._on_yaml_file_selected, tag=FILE_DIALOG_TAG,
            width=700, height=400,
        ):
            dpg.add_file_extension(".yaml", color=(0, 255, 0, 255))
            dpg.add_file_extension(".yml", color=(0, 255, 0, 255))

        with dpg.file_dialog(
            directory_selector=False, show=False,
            callback=self._on_source_file_selected, tag=SOURCE_FILE_DIALOG_TAG,
            width=700, height=400,
        ):
            dpg.add_file_extension(".bin", color=(0, 255, 0, 255))
            dpg.add_file_extension(".rom", color=(0, 255, 0, 255))
            dpg.add_file_extension(".*")

    def _build_custom_card(self) -> None:
        card_theme = self._app.themes.card_button
        btn = dpg.add_button(
            label="Custom 6502 System", width=-1,
            callback=lambda s, a, u: self._on_select_custom(),
            parent=LEFT_PANE_TAG,
        )
        dpg.bind_item_theme(btn, card_theme)

    def _build_custom_form(self) -> None:
        with dpg.group(tag=CUSTOM_FORM_TAG, parent=RIGHT_PANE_TAG, show=False):
            dpg.add_text("Custom System Configuration", color=(255, 255, 0))
            dpg.add_separator()

            with dpg.group(horizontal=True):
                dpg.add_text("System Name:")
                dpg.add_input_text(tag=CUSTOM_NAME_TAG, default_value="My System", width=250)
            with dpg.group(horizontal=True):
                dpg.add_text("CPU Frequency (Hz):")
                dpg.add_input_int(
                    tag=CUSTOM_CPU_HZ_TAG, default_value=1000000,
                    min_value=1, min_clamped=True, width=200,
                )

            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_text("Memory Regions", color=(200, 200, 100))
                dpg.add_button(
                    label="+ Add Region",
                    callback=lambda s, a, u: self._add_region(),
                )
            dpg.add_group(tag=CUSTOM_REGIONS_TAG)

            dpg.add_separator()
            dpg.add_text("Peripherals", color=(200, 200, 100))
            with dpg.group(horizontal=True):
                dpg.add_text("Display:")
                dpg.add_combo(
                    tag=CUSTOM_DISPLAY_TAG,
                    items=["None", "Apple1Display"],
                    default_value="Apple1Display", width=140,
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
                    default_value="Apple1Keyboard", width=140,
                )
                dpg.add_text(" @ 0x")
                dpg.add_input_text(
                    tag=CUSTOM_INPUT_ADDR_TAG, default_value="D010",
                    width=50, uppercase=True, hexadecimal=True, no_spaces=True,
                )

            dpg.add_spacer(height=4)
            dpg.add_text("", tag=CUSTOM_STATUS_TAG)

    # ------------------------------------------------------------------
    # Dynamic memory regions
    # ------------------------------------------------------------------
    def _add_region(
        self, name: str = "", start: str = "0000",
        size: str = "1000", read_only: bool = False,
    ) -> None:
        rid = self._region_counter
        self._region_counter += 1
        self._region_ids.append(rid)

        with dpg.group(tag=f"CustomRegion_{rid}", parent=CUSTOM_REGIONS_TAG):
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag=f"RegionName_{rid}",
                    default_value=name or f"Region{rid}",
                    width=80, hint="Name",
                )
                dpg.add_text("0x")
                dpg.add_input_text(
                    tag=f"RegionStart_{rid}", default_value=start,
                    width=45, uppercase=True, hexadecimal=True, no_spaces=True,
                )
                dpg.add_text("Size: 0x")
                dpg.add_input_text(
                    tag=f"RegionSize_{rid}", default_value=size,
                    width=45, uppercase=True, hexadecimal=True, no_spaces=True,
                )
                dpg.add_checkbox(
                    tag=f"RegionRO_{rid}", label="ROM",
                    default_value=read_only,
                )
                dpg.add_button(
                    label="X", width=24,
                    callback=lambda s, a, u: self._remove_region(u),
                    user_data=rid,
                )
            with dpg.group(horizontal=True):
                dpg.add_text("  Source:")
                dpg.add_input_text(
                    tag=f"RegionSource_{rid}", readonly=True,
                    width=260, hint="(optional binary)",
                )
                dpg.add_button(
                    label="Browse...",
                    callback=lambda s, a, u: self._browse_source(u),
                    user_data=rid,
                )
                dpg.add_button(
                    label="Clear",
                    callback=lambda s, a, u: dpg.set_value(f"RegionSource_{u}", ""),
                    user_data=rid,
                )

    def _remove_region(self, rid: int) -> None:
        if rid in self._region_ids:
            self._region_ids.remove(rid)
            dpg.delete_item(f"CustomRegion_{rid}")

    def _browse_source(self, rid: int) -> None:
        self._source_dialog_target = rid
        dpg.show_item(SOURCE_FILE_DIALOG_TAG)

    def _on_source_file_selected(self, sender: int, app_data: dict, user_data: object) -> None:
        file_path = app_data.get("file_path_name", "")
        if file_path and self._source_dialog_target is not None:
            dpg.set_value(f"RegionSource_{self._source_dialog_target}", file_path)

    def _reset_custom_form(self) -> None:
        for rid in list(self._region_ids):
            self._remove_region(rid)
        self._region_ids.clear()
        self._region_counter = 0
        self._add_region(name="RAM", start="0000", size="1000")

    # ------------------------------------------------------------------
    # Show / refresh
    # ------------------------------------------------------------------
    def show(self) -> None:
        self._refresh_entries()
        dpg.show_item(WINDOW_TAG)

    def _refresh_entries(self) -> None:
        self._entries.clear()
        self._selected_path = None
        self._selected_is_custom = False

        for tag in (PRESET_GROUP_TAG, USER_GROUP_TAG):
            dpg.delete_item(tag, children_only=True)

        for meta in discover_presets():
            self._entries.append(meta)
            self._add_entry_row(meta, PRESET_GROUP_TAG, removable=False)

        valid_paths: list[str] = []
        for path in self._app.settings.user_config_paths:
            meta = load_user_config_metadata(path)
            if meta is not None:
                self._entries.append(meta)
                self._add_entry_row(meta, USER_GROUP_TAG, removable=True)
                valid_paths.append(path)
        self._app.settings.user_config_paths = valid_paths

        if self._entries:
            self._on_select(self._entries[0]["path"])

    def _add_entry_row(self, meta: dict, parent_tag: str, *, removable: bool) -> None:
        card_theme = self._app.themes.card_button
        path = meta["path"]
        with dpg.group(horizontal=True, parent=parent_tag):
            btn = dpg.add_button(
                label=meta["name"],
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

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def _on_select(self, path: str) -> None:
        self._selected_path = path
        self._selected_is_custom = False
        dpg.configure_item(INFO_PANE_TAG, show=True)
        dpg.configure_item(CUSTOM_FORM_TAG, show=False)
        dpg.delete_item(INFO_PANE_TAG, children_only=True)
        meta = next((e for e in self._entries if e["path"] == path), None)
        if meta:
            dpg.add_text(meta["name"], parent=INFO_PANE_TAG, color=(100, 200, 255))
            dpg.add_separator(parent=INFO_PANE_TAG)
            if meta["description"]:
                dpg.add_text(meta["description"].strip(), parent=INFO_PANE_TAG, wrap=480)
            if meta["author"]:
                dpg.add_spacer(parent=INFO_PANE_TAG, height=8)
                dpg.add_text(f"Author: {meta['author']}", parent=INFO_PANE_TAG, color=(180, 180, 180))
            if meta["tags"]:
                tags_str = ", ".join(str(t) for t in meta["tags"])
                dpg.add_text(f"Tags: {tags_str}", parent=INFO_PANE_TAG, color=(180, 180, 180))
            options = meta.get("options", ())
            if options:
                self._render_options(path, options)

    def _render_options(self, path: str, options: tuple[OptionSpec, ...]) -> None:
        """Render a widget per preset option; user changes update self._option_values."""
        dpg.add_spacer(parent=INFO_PANE_TAG, height=12)
        dpg.add_text("Options", parent=INFO_PANE_TAG, color=(255, 255, 0))
        dpg.add_separator(parent=INFO_PANE_TAG)
        selections = self._option_values.setdefault(path, {})
        for opt in options:
            current = selections.get(opt.id, opt.default)
            selections[opt.id] = current
            with dpg.group(horizontal=True, parent=INFO_PANE_TAG):
                dpg.add_text(f"{opt.label}:")
                if opt.kind == "enum":
                    labels = [c.label for c in opt.choices]
                    current_label = next(
                        (c.label for c in opt.choices if c.value == current),
                        labels[0],
                    )
                    dpg.add_combo(
                        items=labels, default_value=current_label, width=180,
                        callback=self._on_enum_option_changed,
                        user_data=(path, opt),
                    )
                elif opt.kind == "int":
                    kwargs: dict = {"default_value": int(current), "width": 140}
                    if opt.min is not None:
                        kwargs["min_value"] = opt.min
                        kwargs["min_clamped"] = True
                    if opt.max is not None:
                        kwargs["max_value"] = opt.max
                        kwargs["max_clamped"] = True
                    dpg.add_input_int(
                        callback=self._on_int_option_changed,
                        user_data=(path, opt),
                        **kwargs,
                    )
                elif opt.kind == "hex":
                    dpg.add_text("0x")
                    dpg.add_input_text(
                        default_value=f"{int(current):X}",
                        width=100, uppercase=True, hexadecimal=True, no_spaces=True,
                        callback=self._on_hex_option_changed,
                        user_data=(path, opt),
                    )
                elif opt.kind == "bool":
                    dpg.add_checkbox(
                        default_value=bool(current),
                        callback=self._on_bool_option_changed,
                        user_data=(path, opt),
                    )
            if opt.description:
                dpg.add_text(f"  {opt.description}", parent=INFO_PANE_TAG, color=(150, 150, 150), wrap=440)

    def _on_enum_option_changed(self, sender: int, app_data: str, user_data: tuple) -> None:
        path, opt = user_data
        for choice in opt.choices:
            if choice.label == app_data:
                self._option_values.setdefault(path, {})[opt.id] = choice.value
                return

    def _on_int_option_changed(self, sender: int, app_data: int, user_data: tuple) -> None:
        path, opt = user_data
        self._option_values.setdefault(path, {})[opt.id] = int(app_data)

    def _on_hex_option_changed(self, sender: int, app_data: str, user_data: tuple) -> None:
        path, opt = user_data
        try:
            self._option_values.setdefault(path, {})[opt.id] = int(app_data, 16) if app_data else opt.default
        except ValueError:
            pass  # keep last good value; let validation catch bad input at launch

    def _on_bool_option_changed(self, sender: int, app_data: bool, user_data: tuple) -> None:
        path, opt = user_data
        self._option_values.setdefault(path, {})[opt.id] = bool(app_data)

    def _on_select_custom(self) -> None:
        self._selected_path = None
        self._selected_is_custom = True
        dpg.configure_item(INFO_PANE_TAG, show=False)
        dpg.configure_item(CUSTOM_FORM_TAG, show=True)
        dpg.set_value(CUSTOM_STATUS_TAG, "")
        self._reset_custom_form()

    def _on_remove_user_config(self, path: str) -> None:
        if path in self._app.settings.user_config_paths:
            self._app.settings.user_config_paths.remove(path)
            save_settings(self._app.settings)
            self._refresh_entries()

    # ------------------------------------------------------------------
    # Launch
    # ------------------------------------------------------------------
    def _on_launch(self) -> None:
        if self._selected_is_custom:
            self._launch_custom()
        elif self._selected_path is not None:
            dpg.hide_item(WINDOW_TAG)
            option_values = self._option_values.get(self._selected_path, {})
            self._app._load_system(self._selected_path, option_values=option_values)

    def _launch_custom(self) -> None:
        name = dpg.get_value(CUSTOM_NAME_TAG) or "Custom System"
        cpu_hz = dpg.get_value(CUSTOM_CPU_HZ_TAG)

        memory = self._collect_regions()
        if memory is None:
            return
        if not memory:
            self._set_status("Add at least one memory region", error=True)
            return

        display = self._collect_display()
        if display is False:
            return

        inputs = self._collect_inputs()
        if inputs is False:
            return

        config = SystemConfig(
            version=1, id="custom", name=name,
            description="Custom system configuration",
            cpu=CpuSpec(type="MOS6502", hz=cpu_hz),
            memory=tuple(memory),
            display=display if display else None,
            inputs=tuple(inputs) if inputs else (),
        )

        try:
            system = System(config)
        except Exception as exc:
            self._set_status(str(exc), error=True)
            return

        dpg.hide_item(WINDOW_TAG)
        self._app._load_system_from_instance(system, name)

    def _collect_regions(self) -> list[MemoryRegion] | None:
        regions: list[MemoryRegion] = []
        for rid in self._region_ids:
            r_name = dpg.get_value(f"RegionName_{rid}").strip()
            if not r_name:
                self._set_status("A memory region has no name", error=True)
                return None
            try:
                r_start = int(dpg.get_value(f"RegionStart_{rid}"), 16)
                r_size = int(dpg.get_value(f"RegionSize_{rid}"), 16)
            except ValueError:
                self._set_status(f"Invalid hex in region '{r_name}'", error=True)
                return None
            if r_size == 0:
                self._set_status(f"Region '{r_name}' has zero size", error=True)
                return None
            r_ro = dpg.get_value(f"RegionRO_{rid}")
            r_source = dpg.get_value(f"RegionSource_{rid}").strip()
            source = f"file:{r_source}" if r_source else None
            regions.append(MemoryRegion(
                name=r_name, start=r_start, size=r_size,
                read_only=r_ro, source=source,
            ))
        return regions

    def _collect_display(self) -> ComponentSpec | None | bool:
        display_type = dpg.get_value(CUSTOM_DISPLAY_TAG)
        if display_type == "None":
            return None
        try:
            addr = int(dpg.get_value(CUSTOM_DISPLAY_ADDR_TAG), 16)
        except ValueError:
            self._set_status("Invalid display address", error=True)
            return False
        return ComponentSpec(type=display_type, address=addr)

    def _collect_inputs(self) -> list[ComponentSpec] | bool:
        input_type = dpg.get_value(CUSTOM_INPUT_TAG)
        if input_type == "None":
            return []
        try:
            addr = int(dpg.get_value(CUSTOM_INPUT_ADDR_TAG), 16)
        except ValueError:
            self._set_status("Invalid input address", error=True)
            return False
        return [ComponentSpec(type=input_type, address=addr)]

    def _set_status(self, text: str, *, error: bool = False) -> None:
        dpg.set_value(CUSTOM_STATUS_TAG, text)
        dpg.configure_item(CUSTOM_STATUS_TAG, color=(255, 80, 80) if error else (80, 255, 80))

    # ------------------------------------------------------------------
    # File dialogs
    # ------------------------------------------------------------------
    def _on_cancel(self) -> None:
        dpg.hide_item(WINDOW_TAG)

    def _on_browse(self) -> None:
        dpg.show_item(FILE_DIALOG_TAG)

    def _on_yaml_file_selected(self, sender: int, app_data: dict, user_data: object) -> None:
        file_path = app_data.get("file_path_name", "")
        if not file_path:
            return
        if file_path not in self._app.settings.user_config_paths:
            self._app.settings.user_config_paths.append(file_path)
            save_settings(self._app.settings)
        self._refresh_entries()
        self._on_select(file_path)
