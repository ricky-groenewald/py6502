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
windows/                  DearPyGui modals and panels (system selector, …)
systems/                  Per-preset configurators (apple1, custom6502)
utils/                    instructionmaps, small helpers
themes.py                 DearPyGui theme factories
py6502ui.py               LEGACY monolithic UI — do not port features into
```

## The one rule that outranks everything

**One coarse `System` call per UI frame. Nothing else.**

The frame loop looks like this:

```python
while dpg.is_dearpygui_running():
    if self.emulator:
        self.emulator.on_update()     # one call → one sim slice
    dpg.render_dearpygui_frame()
```

`on_update` is allowed to call **exactly one** of:

- `System.run_cycles(n)`
- `System.run_for_microseconds(µs)` (usually `16667` at 60 Hz / 1 MHz)

…followed by *reads* against `System.get_framebuffer()`,
`System.get_registers()`, etc. Those reads are cheap: the framebuffer is a
buffer the sim owns and mutates in place, not a per-frame allocation.

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
  `FileMenu`, `NewSystemMenuItem`, `FileMenuSeparator1` — PascalCase with
  a descriptive suffix. Grep-ability matters more than brevity.
- **`init_file`** — the app reads and writes `./py6502ui.ini` via
  `dpg.configure_app(init_file=...)` + `dpg.save_init_file` on exit. Don't
  delete it; it's how window layouts survive restarts.
- **Themes live in `themes.py`** as factory functions that return a theme
  tag. Don't inline colour tuples into widgets.
- **One file per window/panel** under `windows/`. A window class owns its
  own DearPyGui tags, exposes a `show()` method, and cleans up after
  itself when closed.
- **Systems live under `systems/`** as per-preset configurators. Each one
  knows how to present "what are the user-configurable knobs for this
  machine?" and turn the result into a `SystemConfig` the sim can
  consume. `systems/config.py::AVAILABLE_CONFIGS` is the registry.
- **Callbacks are methods**, not lambdas, when they do real work. Lambdas
  are fine for tiny things like `dpg.show_tool(dpg.mvTool_About)`.

## Config-driven UI

The frontend never hard-codes "this is an Apple I" anywhere real. It reads
the same `SystemConfig` IaC format documented in
[`docs/SYSTEM_CONFIG.md`](../../../docs/SYSTEM_CONFIG.md), presents the
configurable knobs from `systems/<preset>.py`, and hands the resolved
config to `py6502.sim.system.System`. Adding a new machine means adding a
preset YAML + a configurator file, not carving a new branch into `app.py`.

When `System.get_framebuffer()` gains support for multiple display
devices (v0.2, when the NES lands with a PPU next to the CPU), the
frontend will pick which display to bind to its texture via the config's
`display` field, not by string-matching peripheral names.

## The legacy `py6502ui.py`

`src/py6502/ui/py6502ui.py` is the pre-restructure monolithic UI. It
wires RAM/ROM/Apple1/BusController up by hand and drives the sim through
the bus directly. It exists as a **feature-parity reference** so that
when we rebuild panels (disassembly, register view, memory monitor,
binary loader) on top of `Py6502App` + `System`, we can see exactly what
the old version did and what we still owe the user.

Rules for touching it:

- **Don't add features to it.** New features go into the `Py6502App` tree.
- **Don't import from it.** It is not part of the public surface.
- **Don't delete it** until `Py6502App` has reached parity on the panel
  you're about to remove. We delete the legacy file in v0.1 as a single
  commit, once parity is done.
- **Imports inside it** should still compile (they were updated during the
  package restructure), so if a rebase breaks them, fix the imports — just
  don't use it as the starting point for new work.

## When adding a new window or panel

1. Create `windows/<name>.py` with a class that owns its tags and a
   `show()` method.
2. If the panel needs to render sim state, decide whether the data it
   needs is already exposed by `System`. If not, **add it to `System`
   first** in a separate PR (or earlier commit) before writing the panel.
3. Open the panel from `app.py`'s menu bar — one menu item, one callback
   method, which instantiates the window class and calls `show()`.
4. Register any new theme factories in `themes.py`, not inline in the
   window file.
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
