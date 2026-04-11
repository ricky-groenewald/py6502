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
├── systemselector.py   "New System" modal, driven by systems/config.py
systems/         Per-preset configurators
├── config.py           AVAILABLE_CONFIGS registry
├── apple1.py           Apple I configurator
└── custom6502.py       Custom 6502 configurator
utils/           Small helpers (instructionmaps, …)
themes.py        DearPyGui theme factories
py6502ui.py      LEGACY monolithic UI — retained as a parity reference
```

## How a frame works

```python
while dpg.is_dearpygui_running():
    if self.emulator:
        self.emulator.on_update()   # one call to the sim
    dpg.render_dearpygui_frame()
```

`on_update` calls exactly one of `System.run_cycles(n)` or
`System.run_for_microseconds(µs)`, then reads back `get_framebuffer()` and
`get_registers()` to update the panels. Everything else about the frame
loop is DearPyGui's problem.

This is the one invariant the frontend has to protect: **one coarse call
to the sim per UI frame**. Anything that loops over CPU cycles from here
is a bug, regardless of whether the tests pass.

## New System flow

1. User opens **File → New System** from the menu bar.
2. `SystemSelector` modal lists the entries in
   `systems/config.py::AVAILABLE_CONFIGS` as cards (currently `APPLE_I`
   and `CUSTOM_6502`).
3. The user picks one; the matching configurator from `systems/<name>.py`
   presents per-preset knobs (memory size, ROM path, …).
4. The configurator produces a `SystemConfig` dataclass (see
   [`docs/SYSTEM_CONFIG.md`](../../../docs/SYSTEM_CONFIG.md)).
5. `Py6502App` hands that config to `System(config)` and attaches the
   resulting instance as `self.emulator`.

Adding a new machine is a new preset YAML + a new configurator file —
**not** a new branch inside `app.py`.

## Legacy UI

`py6502ui.py` is the pre-restructure monolithic frontend. It wires up
`BusController` + `RAM` + `ROM` + `Apple1` directly and hosts the full
set of panels the old version shipped with: disassembly, register view,
memory monitor, binary loader.

It lives on as a **feature-parity reference**. New features go into the
`Py6502App` tree, not into `py6502ui.py`. Once `Py6502App` has caught up
on every panel, the legacy file is deleted in a single v0.1 commit.

Do not import from it. Do not port code out of it; rebuild the panel on
top of `System`'s public API instead.
