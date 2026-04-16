# py6502.sim

The Cython simulator half of `py6502`. Everything in this package is on
the hot path: a cycle-accurate 6502 core, a flat 64K bus, pluggable
addressable components, and (once v0.1 lands) a `System` façade that
builds a whole machine from a declarative config file.

For the full runtime model see [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md);
for the config format see [`docs/SYSTEM_CONFIG.md`](../../../docs/SYSTEM_CONFIG.md);
for the rules Claude follows when editing this package see
[`CLAUDE.md`](CLAUDE.md) next to this file.

## Layout

```
bus/          Component base class, BusController, Memory, EmptyAddress
cpu/          MOS6502 (cycle-accurate)
graphics/     TextDisplay + Font (character-grid renderer)
peripherals/  Apple1; NES components land in v0.2
system/       System façade — draft, intentionally not built yet
assets/       Bundled BIOS ROMs, fonts
```

Each subpackage exposes its public API via its own `__init__.py` shim so
the Cython module names stay an implementation detail. From outside the
package you write:

```python
from py6502.sim.bus import BusController, Memory
from py6502.sim.cpu import MOS6502
from py6502.sim.peripherals import Apple1
```

## The shape of a running machine

1. A `BusController` owns a flat `MappedAddress[0x10000]` table. Every
   16-bit address maps to exactly one `Component` and an offset into that
   component's internal buffer. Unmapped slots fall through to an
   `EmptyAddress` sentinel.
2. `Component` is the cdef base class for anything addressable. Subclasses
   override `cdef unsigned char read(self, unsigned short offset)` and
   `cdef void write(self, unsigned short, unsigned char)`.
3. `MOS6502` is cycle-accurate. It holds a `Registers` struct and a
   precomputed `[256][2]` dispatch table of (addressing-mode, opcode)
   `cdef` function pointers — there is no Python-level decode in steady
   state.
4. A `System` builds all of the above from a `SystemConfig` (see
   `docs/SYSTEM_CONFIG.md`) and exposes a coarse, frontend-facing API:
   `run_cycles`, `run_for_microseconds`, `reset`, `load_binary_at`,
   `get_registers`, `get_framebuffer`. The frontend calls one of these
   once per UI frame.

## Building

Everything in `.pyx` files is compiled by `setup.py` using Cython and a
C compiler; the built `.so` files land next to the sources. Any change to
a `.pyx` or `.pxd` requires a rebuild:

```bash
pip install -e .
```

Compile flags are `-O3 -march=native -flto`, so extensions are tuned to
the host CPU. Moving the repo between machines generally means rebuilding.

## Assets

`assets/` ships bundled BIOS ROMs (currently the Apple 1 wozmon monitor)
and fonts (currently the Apple 1 "Signetics 2513"-style sphere font).
They're packaged via `package-data` in `pyproject.toml` and loaded with
`importlib.resources` against `py6502.sim.assets.<subdir>`. Never
hard-code filesystem paths to them — the package must work when installed
from a wheel with no source tree on disk.

## Performance

The rules that govern every change here are in [`CLAUDE.md`](CLAUDE.md).
The short version, in order of how load-bearing they are:

1. No Python loops in steady state.
2. Coarse APIs only at the Python boundary.
3. Precompute dispatch tables.
4. Direct pointers over object chains.
5. Reuse buffers; no per-frame allocations.

If your change makes any of these less true, it's probably wrong even if
the tests pass.
