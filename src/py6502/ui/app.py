"""
Py6502App — DearPyGui shell that boots a configurable System preset and
renders video + debug panels at 60 Hz. See GH #8 for v0.1 UI scope.
"""
from pathlib import Path
from time import perf_counter

import dearpygui.dearpygui as dpg

from py6502.sim.bus.emptyaddress import UnallocatedAddressError
from py6502.sim.cpu.mos6502 import InvalidOPCode
from py6502.sim.system import System
from py6502.ui.themes import ThemeManager
from py6502.ui.utils.keyhandler import KeyHandler
from py6502.ui.utils.settings import AppSettings, load_settings, save_settings
from py6502.ui.windows.about import AboutWindow
from py6502.ui.windows.binaryloader import BinaryLoaderWindow
from py6502.ui.windows.debug import DebugWindow
from py6502.ui.windows.settings import SettingsWindow
from py6502.ui.windows.systemselector import SystemSelectorWindow
from py6502.ui.windows.video import VideoWindow


FRAME_MICROSECONDS = 16667


class Py6502App:
    def __init__(self) -> None:
        self.context = dpg.create_context()
        self.viewport = dpg.create_viewport(
            title="Py6502",
            width=VideoWindow.TEXTURE_WIDTH * 3 + DebugWindow.WINDOW_WIDTH + 48,
            height=VideoWindow.TEXTURE_HEIGHT * 3 + 80,
        )
        dpg.setup_dearpygui()
        dpg.configure_app(init_file="./py6502ui.ini")
        dpg.set_exit_callback(self._save_init_file)

        self.system: System | None = None
        self.settings: AppSettings = load_settings()
        self._key_buffer: list[int] = []
        self._sim_running = False
        self._sim_error: str | None = None

        self.themes = ThemeManager()
        self.themes.build()

        self._video = VideoWindow(self)
        self._video.build_texture_registry()
        self._build_menu_bar()
        self._video.build()

        self._debug = DebugWindow(self)
        self._debug.build()

        self._settings_window = SettingsWindow(self)
        self._settings_window.build()

        self._system_selector = SystemSelectorWindow(self)
        self._system_selector.build()

        self._binary_loader = BinaryLoaderWindow(self)
        self._binary_loader.build()

        self._about = AboutWindow()
        self._about.build()

        self._key_handler = KeyHandler(self._video, self._key_buffer)
        self._key_handler.build()

        dpg.show_viewport()
        dpg.set_primary_window(VideoWindow.VIDEO_WINDOW_TAG, True)

        self._startup_load()

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------
    def _build_menu_bar(self) -> None:
        with dpg.viewport_menu_bar():
            with dpg.menu(label="File", tag="FileMenu"):
                dpg.add_menu_item(
                    label="New System...", tag="NewSystemMenuItem",
                    callback=self._show_system_selector,
                )
                dpg.add_menu_item(label="Load Binary...", tag="LoadBinaryMenuItem", callback=self._show_binary_loader)
                dpg.add_menu_item(label="Reset System", tag="ResetMenuItem", callback=self._reset_system)
                dpg.add_separator(tag="FileMenuSeparator1")
                dpg.add_menu_item(label="Settings...", tag="SettingsMenuItem", callback=self._show_settings)
                dpg.add_separator(tag="FileMenuSeparator2")
                dpg.add_menu_item(label="Exit", tag="ExitMenuItem", callback=dpg.stop_dearpygui)
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About", callback=self._show_about)

    def _startup_load(self) -> None:
        """Decide what to load on launch based on settings."""
        if self.settings.startup_with_last_system and self.settings.last_system_path:
            path = Path(self.settings.last_system_path)
            if path.exists():
                self._load_system(str(path))
                return
        # Default: show the system selector
        self._system_selector.show()

    def _load_system(self, yaml_path: str) -> None:
        """Load a System from a YAML config and wire it into the UI."""
        self.system = System.from_yaml_file(yaml_path)
        self._apply_settings_to_system()
        self._key_buffer.clear()
        self._sim_error = None
        self._sim_running = True
        self._debug.on_reset()
        self._debug.on_sim_state_changed(running=True)
        self._video.update_framebuffer(self.system.get_framebuffer())
        self._debug.refresh(self.system)
        dpg.focus_item(VideoWindow.VIDEO_WINDOW_TAG)
        # Persist last-used system
        self.settings.last_system_path = yaml_path
        save_settings(self.settings)

    def _apply_settings_to_system(self) -> None:
        if self.system is None:
            return
        self.system.set_invalid_opcode_mode(
            1 if self.settings.halt_on_invalid_opcode else 0,
        )
        self.system.set_unmapped_memory_mode(self.settings.halt_on_unmapped_memory)

    # ------------------------------------------------------------------
    # Per-frame loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        frame_count = 0
        fps_timer = perf_counter()
        while dpg.is_dearpygui_running():
            if self.system is not None:
                if self._sim_running:
                    self._drain_keys_into_system()
                    try:
                        self.system.run_for_microseconds(FRAME_MICROSECONDS)
                    except (InvalidOPCode, UnallocatedAddressError) as exc:
                        self._on_sim_error(exc)
                    self._video.update_framebuffer(self.system.get_framebuffer())
                self._debug.refresh(self.system)
            dpg.render_dearpygui_frame()
            frame_count += 1
            now = perf_counter()
            if now - fps_timer >= 2.0:
                fps = frame_count / (now - fps_timer)
                dpg.set_viewport_title(f"Py6502 - {fps:.0f} FPS")
                frame_count = 0
                fps_timer = now
        dpg.destroy_context()

    def _drain_keys_into_system(self) -> None:
        while self._key_buffer:
            if self.system.send_key(self._key_buffer[0]):
                self._key_buffer.pop(0)
            else:
                break

    def _on_sim_error(self, exc: Exception) -> None:
        self._sim_running = False
        self._sim_error = str(exc)
        self._debug.on_sim_state_changed(running=False, error=str(exc))

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _show_system_selector(self) -> None:
        self._system_selector.show()

    def _show_about(self) -> None:
        self._about.show()

    def _show_binary_loader(self) -> None:
        self._binary_loader.show()

    def _show_settings(self) -> None:
        self._settings_window.show()

    def _play_handler(self) -> None:
        self._sim_running = True
        self._debug.on_sim_state_changed(running=True)
        dpg.focus_item(VideoWindow.VIDEO_WINDOW_TAG)

    def _pause_handler(self) -> None:
        self._sim_running = False
        self._debug.on_sim_state_changed(running=False)

    def _reset_handler(self) -> None:
        if self.system is None:
            return
        self.system.reset()
        self._key_buffer.clear()
        self._sim_error = None
        self._debug.on_reset()
        self._play_handler()
        self._video.update_framebuffer(self.system.get_framebuffer())
        self._debug.refresh(self.system)
        dpg.focus_item(VideoWindow.VIDEO_WINDOW_TAG)

    def _reset_system(self) -> None:
        self._reset_handler()

    def _save_init_file(self) -> None:
        dpg.save_init_file("./py6502ui.ini")
