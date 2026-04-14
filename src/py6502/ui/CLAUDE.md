# CLAUDE.md — py6502.ui

Rules for working in the DearPyGui frontend.

## What this package is

`py6502.ui` is the user-facing shell that drives a `py6502.sim.System`.
It is intentionally thin: the frontend's only job per UI frame is to call
one coarse method on `System` and then hand the resulting framebuffer +
register snapshot to DearPyGui. Everything interesting happens on the sim
side.

```
app.py                    Py6502App — viewport, menu bar, per-frame loop
windows/                  DearPyGui modals and panels
├── video.py              Video output window + texture management
├── debug.py              Debug panel (controls, registers, memory monitor)
├── systemselector.py     System selection modal (presets + user YAMLs)
├── binaryloader.py       Binary load dialog (region + offset)
├── settings.py           Settings window
└── about.py              Custom About dialog
utils/                    Small helpers
├── keyhandler.py         Keyboard input handler (DPG key → Apple I ASCII)
├── instructionmaps.py    Opcode lookup tables
├── paths.py              Per-user data directory (settings, DPG ini, saved configs)
├── presets.py            Preset YAML discovery
└── settings.py           Settings persistence (JSON)
themes.py                 ThemeManager — DearPyGui theme factories
```

## The one rule that outranks everything

**One coarse `System` call per UI frame. Nothing else.**

The frame loop looks like this:

```python
while dpg.is_dearpygui_running():
    now = perf_counter()
    dt = min(now - last_tick_time, MAX_CATCH_UP_SECONDS)
    last_tick_time = now
    if self.system is not None:
        self._drain_keys_into_system()
        self.system.run_for_microseconds(int(dt * 1_000_000))
        self._video.update_framebuffer(self.system.get_framebuffer())
        self._debug.refresh(self.system)
    dpg.render_dearpygui_frame()
```

`dt` is wall-clock-driven, not a fixed per-frame constant: the sim
advances by however much real time elapsed since the last tick, clamped
to `MAX_CATCH_UP_SECONDS` so a paused dialog or a stalled frame can't
trigger a catch-up burst. The sim's effective frequency therefore stays
locked to `cpu_hz` regardless of the host display's refresh rate.

That frame body is allowed to call **exactly one** of:

- `System.run_cycles(n)`
- `System.run_for_microseconds(µs)` (µs derived from wall-clock dt)

…followed by *reads* against `System.get_framebuffer()`,
`System.get_registers()`, etc. Those reads are cheap: the framebuffer is a
buffer the sim owns and mutates in place, not a per-frame allocation.

Debug stepping (`System.step_cycle()`, `System.step_instruction()`) is
the exception: these are called from button callbacks, not the continuous
frame loop.

What you must never do:

- Loop over CPU cycles from the frontend.
- Call a `Component`'s `read`/`write` from the frontend for anything that
  isn't debugger I/O.
- Reach into a Cython class's internals. Go through `System`.
- Allocate a fresh `bytes` / `bytearray` / numpy array every frame to
  copy the framebuffer. Reuse the sim's buffer; let DearPyGui read from
  it.

If you feel a frontend feature needs something `System` doesn't expose,
**add it to `System`**, don't reach around it. Keeping the boundary narrow
is how we stay fast enough to run NES workloads in v0.2.

## DearPyGui conventions

- **Tagged items have string tags**, not raw IDs. Tag names look like
  `PlayButton`, `DebugWindow`, `SystemSelectorPresetGroup` — PascalCase
  with a descriptive suffix. Grep-ability matters more than brevity.
- **`init_file`** — the app reads and writes `py6502.ini` (window layout)
  under the per-user data directory (`utils/paths.dpg_init_path()`), via
  `dpg.configure_app(init_file=...)` + `dpg.save_init_file` on exit. Don't
  delete it; it's how window layouts survive restarts.
- **App settings** live next to it as `py6502_settings.json` (separate from
  the `.ini` which only stores window layout). Both resolve through
  `utils/paths.py`, not hardcoded CWD paths.
- **Themes live in `themes.py`** as a `ThemeManager` class. Don't inline
  colour tuples into widgets.
- **One file per window/panel** under `windows/`. A window class owns its
  own DearPyGui tags, exposes `build()` and optionally `show()`/`hide()`
  methods.
- **Callbacks are methods**, not lambdas, when they do real work.

## Config-driven UI

The frontend never hard-codes "this is an Apple I" anywhere real. It reads
the same `SystemConfig` IaC format documented in
[`docs/SYSTEM_CONFIG.md`](../../../docs/SYSTEM_CONFIG.md), discovers
presets automatically from `py6502.sim.assets.presets/*.yaml`, and hands
the resolved config to `py6502.sim.system.System`. Adding a new machine
means adding a preset YAML — not touching `app.py`.

## When adding a new window or panel

1. Create `windows/<name>.py` with a class that owns its tags and a
   `build()` method.
2. If the panel needs to render sim state, decide whether the data it
   needs is already exposed by `System`. If not, **add it to `System`
   first** in a separate PR (or earlier commit) before writing the panel.
3. Open the panel from `app.py`'s menu bar — one menu item, one callback
   method, which instantiates the window class and calls `show()`.
4. Register any new themes in `ThemeManager`, not inline in the window.
5. Test the panel end-to-end in a running app: boot a preset, open the
   panel, interact with it, and confirm the sim still runs at frame rate.
   Type checks and unit tests don't catch frontend bugs — you have to
   look at the window.

## What "done" looks like for frontend changes

- `python -m py6502` launches and renders at the expected frame rate.
- The feature is reachable from the menu bar or another obvious entry
  point; it's not just a class hiding in `windows/`.
- The feature does not add a per-frame allocation on the hot path.
- Any new `System` API it depends on is documented in
  `docs/ARCHITECTURE.md`.
