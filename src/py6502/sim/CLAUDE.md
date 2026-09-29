# CLAUDE.md — py6502.sim

Rules for working inside the simulator.

## What lives here

`py6502.sim` is the hot path. Everything here is either Cython (`.pyx` +
matching `.pxd`) or a tiny Python shim that exposes it. The runtime model
is documented in full in [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md) —
read that first if you're new to the layout.

```
bus/          Component base class, BusController, Memory, EmptyAddress
cpu/          MOS6502 (cycle-accurate, precomputed [256][2] dispatch)
graphics/     TextDisplay + Font (character-grid renderer)
peripherals/  Apple1Display, Apple1Keyboard, future machines
system/       System façade + YAML loader + component registry
assets/       Bundled BIOS ROMs, fonts, preset configs (shipped via package-data)
```

## Performance rules (load-bearing)

These are the only rules in this file you are not allowed to bend without
an explicit "yes, do it anyway" from Ricky. Every line of Cython in this
package is meant to honour them.

1. **No Python loops in steady state.** If your change adds a `for`/`while`
   that runs per-cycle or per-frame and the loop body reaches Python, it
   is wrong — move the loop (and its body) into a `cdef` function. The one
   Python-visible call the frontend is allowed to make per frame is
   `System.run_cycles` / `run_for_microseconds`, which then spends the
   entire frame inside `cdef` code.
2. **Coarse APIs only at the Python boundary.** `System.run_cycles`,
   `System.run_for_microseconds`, `System.get_framebuffer`,
   `System.get_registers`. The frontend calls one of these per UI frame,
   not one per CPU cycle. Never add a Python-level "tick once" API to a hot
   component — it will get called in a loop.
3. **Precompute dispatch tables.** The 6502 uses a `[256][2]` table of
   `cdef` function pointers for (addressing-mode, opcode). New decoders
   (PPU, mappers) follow the same pattern: build the table once, index
   directly at runtime. Never `if opcode == 0xA9: … elif … elif …` on the
   hot path. The illegal-opcode set is layered on top of the legal table
   by `MOS6502.set_illegal_opcodes()` and is toggled through
   `MOS6502.set_invalid_opcode_mode(mode=2)` — same precomputed-table
   discipline, no Python-level dispatch.
4. **Direct pointers over object chains.** `BusController` stores a flat
   `MappedAddress[0x10000]` table with raw `PyObject*` pointers to the
   owning `Component` plus the component's internal offset. A CPU read is
   one table lookup, one C cast, one virtual `cdef` call — that's the
   bar. Don't walk a list of components on every access.
5. **Reuse buffers; no per-frame allocations.** Framebuffers, keyboard
   buffers, scanline buffers — allocate once at construction, mutate in
   place. Every `bytes(...)` / `bytearray(...)` / list-comprehension on
   the hot path is a regression.
6. **`cdef inline` the tiny helpers.** Small address-math / flag-update
   helpers should be `cdef inline` so the C compiler can fold them into
   their caller under `-O3 -flto`.
7. **Contiguous C arrays** (`unsigned char mem[0x10000]`, struct-of-arrays
   for register files) over `object` fields whenever the data is numeric
   and fixed-size.
8. **`@cython.boundscheck(False)` / `@cython.wraparound(False)`** at the
   top of modules that do heavy index work, but only after you are sure
   the indices can't go out of bounds. A segfault in a Cython array is
   worse than a `IndexError`.

If you catch yourself writing "just this one Python call", stop and ask
whether the caller is on the hot path. If it is, fix it. If you're
honestly not sure, flag it in the PR description — Ricky will tell you.

## Cython conventions

- **Every `.pyx` has a matching `.pxd`** that declares its `cdef class`
  members, `cdef` functions, and any C structs. Python code `import`s the
  module; other Cython modules `cimport` the `.pxd`. Don't declare types in
  only one place.
- **Module naming follows the Python package**: `py6502.sim.bus.component`,
  `py6502.sim.cpu.mos6502`, etc. Imports inside the package are fully
  qualified (`from py6502.sim.bus.component cimport Component`) — not
  relative, not legacy `py6502sim.*`.
- **New Cython modules must be added to `setup.py`**. Add an `ext(...)`
  entry for the new `.pyx`, and if it lives in a new subpackage, extend
  `include_dirs` too. Rebuild with `pip install -e .` — editable installs
  still rebuild the extensions.
- **Public Python API goes through the subpackage `__init__.py`**
  (e.g. `from py6502.sim.bus import BusController, Memory`). That lets us
  keep the `.pyx` module names as an implementation detail.
- **Asset loading uses `importlib.resources`** against
  `py6502.sim.assets.<subdir>`. Never hard-code filesystem paths.

## Adding a new component

The recipe for a new addressable device (RAM region, ROM, peripheral,
mapper, PPU register window, …):

1. Create `py6502/sim/<subpackage>/<name>.pxd` + `.pyx`.
2. The class inherits from `py6502.sim.bus.component.Component` and
   overrides `cdef int read(self, unsigned short offset) except -1` and
   `cdef int write(self, unsigned short offset, unsigned char value) except -1`.
   Both return the byte (0..255); `-1` is reserved as the error sentinel
   that lets Cython propagate exceptions cheaply, so never return it on
   purpose. `offset` is already the component-relative offset — the
   `BusController` computes it for you.
3. Allocate every buffer the component will ever need at construction —
   in `__init__` right after `super().__init__`, as the existing
   components do — and free it in `__dealloc__`. No allocations in
   `read` / `write`.
4. Register the class string → class mapping in the component registry
   (see `docs/SYSTEM_CONFIG.md` §Component registry) so it is reachable
   from IaC configs.
5. Add an `ext(...)` line in `setup.py`.
6. Rebuild (`pip install -e .`) and write a pytest fixture that maps the
   new component onto a minimal `System` and round-trips a read/write
   through it.

## Peripherals specifically

**Peripherals do not own their clock.** The cycle loop lives in
`BusController.run_cycles` (invoked from `System.run_cycles` /
`run_for_microseconds`), which executes `N` calls to `MOS6502.clock()` in
pure Cython and then fans out a single tick-hook call per registered
component. A peripheral that needs cycle-level accuracy overrides
`cdef void on_cycles_elapsed(self, unsigned long n)` and subscribes via
`bind()` — see `Apple1Display` for the reference implementation of the
DSP busy-timer.

### Accuracy First

Hardware timing is a contract. `Apple1Display`'s DSP bit 7 stays busy
for exactly one NTSC frame (≈16,667 cycles at 1 MHz, computed at
`bind()` time as `round(cpu_hz / 60)` so the timing scales with the
configured clock — not hardcoded, not "some cycles", not "cleared at
the next batch boundary"). Test
`test_dsp_busy_timing_via_system_run_cycles` locks this at batch
granularity so future refactors can't silently regress it. When you add
a peripheral with hardware-observable timing, write the equivalent test
up front and keep it cycle-exact.

## Testing

- pytest fixtures live in `tests/`. Each fixture builds a minimal
  `System` with exactly the components the test needs.
- **Klaus Dormann 6502 functional test** and **Bruce Clark decimal test**
  run by hand today from a local scratch script; they are not in the
  repo or in CI. #50 (v0.2) adds thin conformance runners under
  `scripts/` that fetch the upstream GPL-3.0 binaries at run time, so
  the same command works locally and in CI without bundling GPL bytes.
  A Klaus run takes ~96M cycles.
- The **hot-path guard** (`tests/test_hot_path.py`) fails if any Python
  function runs inside a sim call, and names the function. Treat a
  failure after your change as a real failure; there is no threshold to
  bump. It cannot see C-API work inside compiled code (dict lookups,
  calls through untyped references), so also compare throughput before
  and after with the method in
  [`docs/PERFORMANCE.md`](../../../docs/PERFORMANCE.md).
- No Python unit test is allowed to reach *into* a Cython class's internals
  with `cdef` access. Go through the Python-visible API. If the Python API
  doesn't expose something you need to verify, that's worth a conversation
  before adding a test hook.

## When you're about to touch the CPU core

`cpu/mos6502.pyx` is the most load-bearing file in the repo. Changes here
need:

- The full Klaus + Bruce Clark suites green (run by hand until #50).
- Before/after throughput, measured back to back with the method in
  [`docs/PERFORMANCE.md`](../../../docs/PERFORMANCE.md).
- A note in the PR description explaining *why* the change is correct,
  not just *what* it does.

The dispatch table is the most-scrutinised data structure in the project.
Reorder it at your peril.
