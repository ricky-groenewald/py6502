---
name: new-peripheral
description: Scaffold a new addressable component under `src/py6502/sim/peripherals/` (or a RAM/ROM region, PPU register window, mapper, etc. — anything that lives on the bus). Generates matching `.pxd` + `.pyx` with the Component subclass shape, registers the module in `setup.py`, adds the component to the registry described in `docs/SYSTEM_CONFIG.md`, and prints a rebuild + smoke-test checklist. Does not implement read/write logic beyond trivial stubs.
---

# new-peripheral

A scaffolding skill. It sets up the boilerplate for a new `Component`
subclass so the human (or a follow-up edit) only has to fill in the
actual `read` / `write` logic and any internal buffers.

## When to use

- Adding a new bus-mapped device: a peripheral chip, a PIA, a VIA, a
  mapper register window, a PPU control register block, a specialised
  ROM region with bank switching, etc.
- Adding a new machine's top-level peripheral (e.g. a `Famicom` glue
  class in v0.2).

Don't use this for:

- Pure Python helpers (they don't go under `sim/`).
- Anything that isn't addressable from the 6502's bus.
- Modifications to an existing component — edit the file directly.

## Inputs the skill expects

Ask the caller (once, up front) for:

1. **Name** in PascalCase, e.g. `VIA6522`, `MMC1`, `C64CIA`.
2. **Subpackage** under `src/py6502/sim/`: usually `peripherals`, but
   could be a new one like `mappers` if the PR is introducing it.
3. **Registry string** — the string used to refer to the component from
   a `SystemConfig` YAML file. Registry keys are the PascalCase class
   name, e.g. `VIA6522`, `MMC1` (see `Apple1Display` / `Apple1Keyboard`
   in `src/py6502/sim/system/registry.py`). Default: the class name.
4. **Short one-line description** for the class docstring and the
   registry entry.

If the subpackage doesn't exist yet, confirm that's intentional (new
subpackage = new `include_dirs` entry in `setup.py` + new `__init__.py`).

## What the skill produces

### 1. `src/py6502/sim/<subpackage>/<name_lower>.pxd`

```cython
from py6502.sim.bus.component cimport Component

cdef class <Name>(Component):
    # Declare any cdef attributes (buffers, state) here.
    # Example:
    #     cdef unsigned char[0x100] _regs
    pass
```

### 2. `src/py6502/sim/<subpackage>/<name_lower>.pyx`

```cython
# cython: boundscheck=False, wraparound=False
"""
<short description>
"""
from py6502.sim.bus.component cimport Component

cdef class <Name>(Component):
    """<short description>"""

    def __init__(self) -> None:
        # size = number of bus addresses the component occupies. The
        # base address is NOT a constructor argument — the bus assigns
        # it in BusController.add_component.
        super().__init__(<size>, "<Name>")

    cdef int read(self, unsigned short offset) except -1:
        # offset is component-relative; BusController already mapped it.
        # Return the byte (0..255). -1 is reserved as the error sentinel.
        return 0

    cdef int write(self, unsigned short offset, unsigned char value) except -1:
        # Return the byte written (0..255). -1 is reserved as the error sentinel.
        return value
```

Buffers (a framebuffer, a FIFO) are allocated once at construction and
never reallocated. The existing components `malloc` them in `__init__`
right after `super().__init__` and free them in `__dealloc__`; see
`Apple1Keyboard` for the pattern. Use `__cinit__` only if the buffer
must exist before any Python-level `__init__` can run.

Optional overrides live on `Component` and are documented in
`src/py6502/sim/bus/component.pyx`: `bind(system)` for cross-component
refs and tick-hook subscription, `on_cycles_elapsed(n)` for batch-end
cycle accounting, `get_framebuffer()` / `render_framebuffer()` for
displays, and `send_input()` / `clear_input()` for keyboard-like devices.

The header comment + class docstring must contain the short description
the caller supplied. No other comments.

### 3. `setup.py` — add an `ext(...)` entry

Insert a new line in the `extensions` list, grouped with its siblings
(e.g. other peripherals):

```python
ext("py6502.sim.<subpackage>.<name_lower>", "src/py6502/sim/<subpackage>/<name_lower>.pyx"),
```

If the subpackage is new, also add its source directory to
`include_dirs`.

### 4. `src/py6502/sim/<subpackage>/__init__.py` — re-export

Add:

```python
from py6502.sim.<subpackage>.<name_lower> import <Name>  # noqa: F401
```

Create the `__init__.py` with a one-line docstring if it doesn't exist.

### 5. Component registry entry

Add the class to `COMPONENT_REGISTRY` in
`src/py6502/sim/system/registry.py`, grouped with its siblings:

```python
"<Name>": <Name>,
```

The key is the PascalCase class name. Import the class at the top of
`registry.py` via the subpackage `__init__.py` shim, not the `.pyx`
module directly.

## Post-scaffold checklist the skill prints

After generating files, print this exact checklist so the caller can tick
it off:

```
[ ] pip install -e .                      # rebuild extensions
[ ] python -c "from py6502.sim.<subpackage> import <Name>"
                                          # import smoke test
[ ] Write a pytest fixture that maps <Name> onto a minimal System
    and round-trips one read and one write through it.
[ ] Fill in buffers and read/write logic.
[ ] read/write return the byte (0..255) on every path; never return -1.
[ ] Update docs/SYSTEM_CONFIG.md appendix if this adds a new preset.
[ ] Run sim-perf-reviewer on the new file.
```

## What the skill must not do

- **Do not implement `read` / `write` logic.** Stubs only. The author
  fills in the actual behaviour in a follow-up edit — that's where the
  interesting work is and it needs a human's judgement.
- **Do not allocate anything in `read`/`write`.** Buffers are allocated
  once at construction (`__init__`, or `__cinit__` for buffers that must
  never be reallocated).
- **Do not add Python-visible tick methods.** If the new component needs
  to do per-cycle work, the shape is a `cdef` method on `Component`, not
  a Python method the frontend calls in a loop.
- **Do not run `pip install -e .`.** The checklist tells the human to do
  it. Build side-effects from a scaffolding skill cause more problems
  than they solve.

## References

- `src/py6502/sim/CLAUDE.md` — the rules every new component must
  follow.
- `docs/ARCHITECTURE.md` — how components fit into `BusController` and
  `System`.
- `docs/SYSTEM_CONFIG.md` — the IaC config format and the component
  registry shape.
- `src/py6502/sim/peripherals/apple1_display.pyx` — the canonical
  reference for a peripheral with hardware-observable timing
  (DSP busy bit, batch-end tick hook, `bind()` wiring against
  `cpu_hz`).
- `src/py6502/sim/peripherals/apple1_keyboard.pyx` — the canonical
  reference for an input peripheral (FIFO buffer, `send_input` /
  `clear_input` overrides).
