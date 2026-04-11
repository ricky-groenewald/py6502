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
3. **Registry string** — the lowercase string used to refer to the
   component from a `SystemConfig` YAML file, e.g. `via6522`, `mmc1`.
   Default: lowercase of the class name.
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

    def __cinit__(self, unsigned short address, unsigned short size):
        # Allocate every buffer the component will ever need here.
        # No allocations in read/write.
        pass

    cdef unsigned char read(self, unsigned short offset):
        # offset is component-relative; BusController already mapped it.
        return 0

    cdef void write(self, unsigned short offset, unsigned char value):
        pass
```

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

Once the registry file lives at `src/py6502/sim/system/registry.py` (it
will be created when the `system` module is (re)built against the IaC
spec), add:

```python
"<registry-string>": <Name>,
```

Until that file exists, print a clear note that the registry entry is
pending the `system` rewrite and can't be wired up yet — don't silently
skip it.

## Post-scaffold checklist the skill prints

After generating files, print this exact checklist so the caller can tick
it off:

```
[ ] pip install -e .                      # rebuild extensions
[ ] python -c "from py6502.sim.<subpackage> import <Name>"
                                          # import smoke test
[ ] Write a pytest fixture that maps <Name> onto a minimal System
    and round-trips one read and one write through it.
[ ] Fill in __cinit__ buffers and read/write logic.
[ ] Update docs/SYSTEM_CONFIG.md appendix if this adds a new preset.
[ ] Run sim-perf-reviewer on the new file.
```

## What the skill must not do

- **Do not implement `read` / `write` logic.** Stubs only. The author
  fills in the actual behaviour in a follow-up edit — that's where the
  interesting work is and it needs a human's judgement.
- **Do not allocate anything in `read`/`write`.** The template explicitly
  puts allocations in `__cinit__`.
- **Do not add Python-visible tick methods.** If the new component needs
  to do per-cycle work, the shape is a `cdef` method on `Component`, not
  a Python method the frontend calls in a loop.
- **Do not run `pip install -e .`.** The checklist tells the human to do
  it. Build side-effects from a scaffolding skill cause more problems
  than they solve.
- **Do not touch the legacy `py6502ui.py`.**

## References

- `src/py6502/sim/CLAUDE.md` — the rules every new component must
  follow.
- `docs/ARCHITECTURE.md` — how components fit into `BusController` and
  `System`.
- `docs/SYSTEM_CONFIG.md` — the IaC config format and the component
  registry shape.
- `src/py6502/sim/peripherals/apple1.pyx` — the canonical example of a
  peripheral, warts and all. Note that its `clock()` method is a v0.1
  anti-pattern that will be removed; do not copy that loop shape into
  new work.
