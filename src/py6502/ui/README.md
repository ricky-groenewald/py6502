# py6502.ui

The DearPyGui frontend for `py6502`. A deliberately thin shell whose job
per frame is to call one coarse method on a `py6502.sim.System` instance
and hand the result to DearPyGui.

For the rules this package follows when edited by Claude, see
[`CLAUDE.md`](CLAUDE.md). For the runtime contract between the frontend
and the simulator, see [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md).

## Running

```bash
pip install -e .
python -m py6502
```

Entry point: `src/py6502/__main__.py` → `Py6502App().run()`.

## Layout

```
app.py           Py6502App — viewport, menu bar, per-frame loop
windows/         DearPyGui modals and panels
├── video.py              Video output window + texture management
├── debug.py              Debug panel (controls, registers, memory monitor)
├── systemselector.py     System selection modal (presets + user YAMLs)
├── binaryloader.py       Binary load dialog (region + offset)
├── settings.py           Settings window
└── about.py              Custom About dialog
utils/           Small helpers
├── keyhandler.py         Keyboard input handler
├── instructionmaps.py    Opcode lookup tables
├── presets.py            Preset YAML discovery
└── settings.py           Settings persistence (JSON)
themes.py        ThemeManager — DearPyGui theme factories
```

## How a frame works

```python
while dpg.is_dearpygui_running():
    if self.system is not None:
        if self._sim_running:
            self._drain_keys_into_system()
            self.system.run_for_microseconds(FRAME_MICROSECONDS)
            self._video.update_framebuffer(self.system.get_framebuffer())
        self._debug.refresh(self.system)
    dpg.render_dearpygui_frame()
```

This is the one invariant the frontend has to protect: **one coarse call
to the sim per UI frame**. Anything that loops over CPU cycles from here
is a bug, regardless of whether the tests pass.

## New System flow

1. On startup the **System Selector** modal appears (unless "Start with
   last used system" is enabled in settings and a previous system is
   available).
2. The selector auto-discovers preset YAMLs from
   `py6502.sim.assets.presets/` and shows any previously loaded user
   configs from `py6502_settings.json`.
3. The user picks a preset or browses for a custom YAML file.
4. `Py6502App._load_system(yaml_path)` calls `System.from_yaml_file`,
   wires the resulting instance into the UI, and persists the choice.

Adding a new machine is a new preset YAML in the assets directory —
**not** a new branch inside `app.py`.
