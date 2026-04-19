"""
Py6502App — DearPyGui shell that boots a configurable System preset and
renders video + debug panels at the display's native refresh rate. The
simulator is paced by wall-clock delta so its effective frequency stays
locked to the configured ``cpu_hz`` regardless of UI frame rate. See
GH #8 for v0.1 UI scope.
"""
from pathlib import Path
from time import perf_counter

import dearpygui.dearpygui as dpg

from py6502.sim.bus.emptyaddress import UnallocatedAddressError
from py6502.sim.cpu.mos6502 import InvalidOPCode
from py6502.sim.system import ConfigError, System, from_yaml_file_with_options
from py6502.ui.themes import ThemeManager
from py6502.ui.utils import paths
from py6502.ui.utils.keyhandler import KeyHandler
from py6502.ui.utils.settings import AppSettings, load_settings, save_settings
from py6502.ui.windows.about import AboutWindow
from py6502.ui.windows.binaryloader import BinaryLoaderWindow
from py6502.ui.windows.debug import DebugWindow
from py6502.ui.windows.settings import SettingsWindow
from py6502.ui.windows.systemselector import SystemSelectorWindow
from py6502.ui.windows.video import VideoWindow


# Cap on the dt the sim can be asked to advance in a single frame.
# A long pause (modal dialog, OS hiccup, sleeping laptop) would
# otherwise translate into a massive catch-up burst and visible stutter.
# 50 ms ≈ 50,000 cycles at 1 MHz, which is still inside one frame's
# wall-clock budget at 60 FPS.
MAX_CATCH_UP_SECONDS = 0.05


def _format_hz(hz: float) -> str:
    if hz >= 1_000_000:
        return f"{hz / 1_000_000:.2f} MHz"
    if hz >= 1_000:
        return f"{hz / 1_000:.2f} kHz"
    return f"{hz:.0f} Hz"


class Py6502App:
    def __init__(self) -> None:
        self.context = dpg.create_context()
        self.viewport = dpg.create_viewport(
            title="Py6502",
            width=VideoWindow.TEXTURE_WIDTH * 3 + DebugWindow.WINDOW_WIDTH + 80,
            height=VideoWindow.TEXTURE_HEIGHT * 3 + 120,
        )
        dpg.setup_dearpygui()
        dpg.configure_app(init_file=str(paths.dpg_init_path()))
        dpg.set_exit_callback(self._save_init_file)

        self.system: System | None = None
        self._system_name: str = ""
        self.settings: AppSettings = load_settings()
        self._key_buffer: list[int] = []
        # Pause/error gate for the per-frame loop. Cleared by Pause and
        # by sim errors; set by Play and by a successful system load.
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
                try:
                    self._load_system(str(path))
                    return
                except ConfigError:
                    pass  # stale persisted state — fall through to selector
        # Default: show the system selector
        self._system_selector.show()

    def _load_system(
        self,
        yaml_path: str,
        option_values: dict[str, object] | None = None,
    ) -> None:
        """Load a System from a YAML config and wire it into the UI.

        If ``option_values`` is None, falls back to whatever values were last
        used for this path (from settings). An explicit ``{}`` means "use the
        preset's declared defaults".
        """
        if option_values is None:
            option_values = dict(self.settings.last_option_values.get(yaml_path, {}))
        config = from_yaml_file_with_options(yaml_path, option_values)
        system = System(config)
        self._wire_system(system, config.name)
        self.settings.last_system_path = yaml_path
        self.settings.last_option_values[yaml_path] = dict(option_values)
        save_settings(self.settings)

    def _wire_system(self, system: System, name: str = "") -> None:
        """Common setup after a System is constructed."""
        self.system = system
        self._system_name = name
        self._apply_settings_to_system()
        self._key_buffer.clear()
        self._sim_error = None
        self._sim_running = True
        self._debug.on_reset()
        self._debug.on_sim_state_changed(running=True)
        # Rebind the raw texture onto the new display's RGBA buffer.
        # Every subsequent frame reads directly from that buffer, so
        # no per-frame copy is needed. sync_display populates the buffer
        # with the current sim state (cursor visible, reset banner,
        # etc.) so the very first rendered frame isn't all zeros —
        # run_for_microseconds would also do this at the next tick, but
        # that's one full frame of blank we'd rather not see.
        self._video.bind_system_framebuffer(self.system.get_framebuffer())
        self.system.sync_display()
        self._debug.refresh(self.system)
        dpg.focus_item(VideoWindow.VIDEO_WINDOW_TAG)

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
        # The whole frontend lives inside this loop. Per the
        # one-coarse-call-per-frame contract (see ui/CLAUDE.md), each
        # iteration calls ``System.run_for_microseconds`` exactly once —
        # the sim does the rest in compiled Cython.
        frame_count = 0
        # Cycles *issued* to the sim, not measured back from it. Used
        # purely for the FPS / Hz readout in the viewport title; the sim
        # is not CPU-bound at v0.1 cpu_hz so issued ≈ delivered.
        cycles_accum = 0
        last_tick_time = perf_counter()
        fps_timer = last_tick_time
        while dpg.is_dearpygui_running():
            now = perf_counter()
            # Wall-clock dt drives the sim, with MAX_CATCH_UP_SECONDS as
            # the safety cap (see the constant's comment for why).
            dt = min(now - last_tick_time, MAX_CATCH_UP_SECONDS)
            last_tick_time = now
            if self.system is not None:
                if self._sim_running:
                    self._drain_keys_into_system()
                    micros = int(dt * 1_000_000)
                    try:
                        self.system.run_for_microseconds(micros)
                    except (InvalidOPCode, UnallocatedAddressError) as exc:
                        # _on_sim_error flips _sim_running off, so we
                        # won't re-enter this branch until the user
                        # acknowledges via Reset/Play.
                        self._on_sim_error(exc)
                    else:
                        cycles_accum += (micros * self.system.cpu_hz) // 1_000_000
                # Refresh the debug panel even when paused so single-step
                # buttons reflect the current sim state immediately. The
                # video texture is bound to the sim's RGBA buffer by
                # _wire_system, so no explicit upload is needed here —
                # DPG re-uploads from the bound memory on render.
                self._debug.refresh(self.system)
            dpg.render_dearpygui_frame()
            frame_count += 1
            elapsed = now - fps_timer
            if elapsed >= 2.0:
                # Throttled viewport-title update (every ~2 s).
                fps = frame_count / elapsed
                avg_hz = cycles_accum / elapsed
                suffix = f" - {self._system_name}" if self._system_name else ""
                dpg.set_viewport_title(
                    f"Py6502 - {fps:.0f} FPS - {_format_hz(avg_hz)}{suffix}"
                )
                frame_count = 0
                cycles_accum = 0
                fps_timer = now
        dpg.destroy_context()

    def _drain_keys_into_system(self) -> None:
        while self._key_buffer:
            if self.system.send_key(self._key_buffer[0]):
                self._key_buffer.pop(0)
            else:
                break

    def _on_sim_error(self, exc: Exception) -> None:
        # Hard-stop the sim. Stays stopped until Reset (which clears the
        # error and re-enables Play); plain Play won't recover, since
        # the failing instruction is still where PC points.
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
        self._debug.refresh(self.system)
        dpg.focus_item(VideoWindow.VIDEO_WINDOW_TAG)

    def _reset_system(self) -> None:
        self._reset_handler()

    def _save_init_file(self) -> None:
        dpg.save_init_file(str(paths.dpg_init_path()))
