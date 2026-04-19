# Architecture

> **Audience:** contributors and maintainers. This document describes how
> the pieces of py6502 fit together at runtime. For the declarative
> *config* format, see [SYSTEM_CONFIG.md](SYSTEM_CONFIG.md). For the
> non-negotiable performance rules, see
> [src/py6502/sim/CLAUDE.md](../src/py6502/sim/CLAUDE.md).

---

## 1. The 30-second picture

```
 ┌───────────────────────────────────┐
 │           py6502.ui               │   Pure-Python DearPyGui frontend.
 │   Py6502App — one on_update()     │   One coarse call per UI frame.
 │   per frame drives the emulator.  │
 └──────────────┬────────────────────┘
                │  System.run_for_microseconds(16667)
                ▼
 ┌───────────────────────────────────┐
 │    py6502.sim.system.System       │   Cython orchestrator. Built from a
 │    owns bus(es), clocks them,     │   SystemConfig. Single coarse API
 │    holds direct display ref.      │   the UI calls per frame.
 └──────────────┬────────────────────┘
                │  _buses["main"].run_cycles(N)
                ▼
 ┌───────────────────────────────────┐
 │  py6502.sim.bus.BusController     │   Flat 64K MappedAddress table +
 │  routes reads/writes through a    │   PyObject* to the owning
 │  direct PyObject* table.          │   Component. No Python in steady
 └──────┬────────────┬───────────────┘   state.
        │            │
        ▼            ▼
 ┌──────────┐   ┌────────────────┐
 │  MOS6502 │   │   Components   │       Memory, Apple1, NES PPU, etc.
 │  cycle-  │   │  (cdef classes)│       Subclass Component, override
 │  accurate│   │                │       cdef read/write.
 └──────────┘   └────────────────┘
```

The key invariants:

- **Everything performance-critical is Cython.** No Python loops anywhere
  in the clock path.
- **The frontend makes exactly one call per UI frame.** Inside that call,
  thousands of 6502 cycles execute entirely in compiled C.
- **Components are addressed through a flat 64K table.** Reading or
  writing a bus address is a single pointer dereference plus a `cdef`
  virtual call — no hash lookups, no Python attribute access.

---

## 2. Package layout

```
src/py6502/
├── __init__.py
├── __main__.py                    # python -m py6502 → Py6502App().run()
├── sim/                           # Cython simulator (hot path)
│   ├── __init__.py
│   ├── assets/                    # Fonts, BIOSes, preset configs
│   │   ├── bios/
│   │   ├── fonts/
│   │   └── presets/               # Preset .yaml configs
│   ├── bus/
│   │   ├── component.pxd/.pyx     # Component base class + tick hooks
│   │   ├── buscontroller.pxd/.pyx # Flat 64K MappedAddress table
│   │   ├── memory.pxd/.pyx        # RAM / ROM region
│   │   └── emptyaddress.pxd/.pyx  # Sentinel for unmapped addresses
│   ├── cpu/
│   │   └── mos6502.pxd/.pyx       # Cycle-accurate 6502
│   ├── graphics/
│   │   └── textdisplay.pxd/.pyx   # Character-grid framebuffer + Font
│   ├── peripherals/
│   │   ├── apple1_display.pxd/.pyx  # DSP + DSPCR + NTSC-frame busy timer
│   │   └── apple1_keyboard.pxd/.pyx # KBD + KBDCR + circular FIFO buffer
│   └── system/
│       ├── config.py              # Frozen dataclass representation
│       ├── registry.py            # Type-name → class registry
│       ├── loader.py              # YAML → SystemConfig + validation
│       └── system.pxd/.pyx        # Orchestrator
└── ui/                            # DearPyGui frontend (pure Python)
    ├── __init__.py
    ├── app.py                     # Py6502App — menu bar, per-frame loop
    ├── themes.py                  # ThemeManager — DearPyGui theme factories
    ├── utils/                     # Key handler, settings, preset discovery
    └── windows/                   # Video, debug, system selector, etc.
```

---

## 3. The simulator

### 3.1 `Component` — the base primitive

`Component` is the `cdef` base class in `py6502.sim.bus.component`:

```cython
cdef class Component:
    cdef unsigned int _size
    cdef str _name

    cdef unsigned char read(self, unsigned short address) except *:
        return 0

    cdef unsigned char write(self, unsigned short address, unsigned char data) except *:
        return 0

    cdef void bind(self, object system):
        pass

    cdef void on_cycles_elapsed(self, unsigned long n):
        pass

    cdef inline unsigned int get_size(self): ...
    cdef inline str get_name(self): ...

    # Optional overrides for display / input devices
    cdef object get_framebuffer(self): ...  # default: None (pure getter)
    cdef void render_framebuffer(self): ... # default: no-op (per-frame refresh)
    cdef bint send_input(self, unsigned char char_): ...  # default: False
    cdef void clear_input(self): ...        # default: no-op
```

Every addressable thing in the simulator — RAM, ROM, peripherals, even
the bus controller itself — is a `Component`. The `read` and `write`
methods are **`cdef`**, not `cpdef`, so they're called through Cython's
internal virtual table with zero Python overhead once Cython knows the
object is a `Component`.

`bind(system)` is a late-binding hook fired by `System.__init__` after
every component has been wired onto its bus. Components that need
cross-component references or a tick-hook subscription grab them here.
`on_cycles_elapsed(n)` is the cycle-accounting hook fired exactly once
per `BusController.run_cycles(N)` batch for every component that
registered via `system.register_tick_hook(self)` — **not once per
cycle**. See `Apple1Display` for the reference use: decrementing a
DSP busy counter without touching the CPU hot path.

Subclasses override `read` and `write` to implement their behavior:

```cython
cdef class Memory(Component):
    cdef unsigned char[::1] _data
    cdef bint _read_only

    cdef unsigned char read(self, unsigned short address) except *:
        return self._data[address]

    cdef unsigned char write(self, unsigned short address, unsigned char data) except *:
        if not self._read_only:
            self._data[address] = data
        return data
```

### 3.2 `BusController` — the flat address table

The bus is conceptually a 64 KiB array where each entry tells you
*which component owns this address* and *what internal offset that
component uses*:

```cython
ctypedef struct MappedAddress:
    PyObject* component         # owning Component, borrowed PyObject*
    unsigned int internal_address

cdef class BusController(Component):
    cdef MappedAddress _component_address_map[0x10000]
    cdef MOS6502 _processor
    cdef EmptyAddress _empty_address
```

When the CPU executes `LDA $C000`, the bus controller:

1. Indexes `_component_address_map[0xC000]` — single pointer arithmetic.
2. Casts the `PyObject*` to `Component` and calls its `cdef read()` —
   single C virtual call.
3. Returns the result.

**No dict lookup, no Python call, no hash, no bounds check** (bounds
checking is explicitly disabled via `@boundscheck(False)` because the
address is already masked to 16 bits).

Unmapped addresses point at an `EmptyAddress` sentinel instance. The
sentinel's behavior is user-configurable at runtime:

- **Open bus** (default): reads return the last value on the data bus,
  writes are silently dropped. This matches real 6502 hardware behavior.
- **Crash**: reads and writes raise `UnallocatedAddressError`, which
  propagates through the `except *` call chain to the UI. The UI pauses
  the simulator and only allows a reset to resume.

Invalid opcodes follow a similar pattern in `MOS6502.load_op_code()`:

- **Crash** (default): raises `InvalidOPCode` with the opcode byte and
  address. The UI catches it and pauses.
- **NOP**: the invalid opcode is treated as a 2-cycle implied NOP and
  execution continues.

Both settings are toggled through `System.set_unmapped_memory_mode()`
and `System.set_invalid_opcode_mode()`, exposed in the UI's Settings
menu.

`BusController.add_component(component, address_start)`:

- Validates that `component.get_size() + address_start <= 0x10000`.
- Validates that no slot in the range currently points at anything
  other than the `EmptyAddress` sentinel (no overlap).
- Fills every slot in the range with the component pointer and the
  right internal offset.
- Manages `Py_INCREF`/`Py_DECREF` so Python refcounting stays correct.

Higher-level concerns like mirroring, banking, and bus splits are
explicitly **not** the bus controller's job — those are the orchestrator's
problem.

### 3.3 `MOS6502` — cycle-accurate 6502

The CPU holds a `Registers` struct (`PC`, `SP`, `A`, `X`, `Y`, `P`, plus
some bus-snapshot fields used for the debugger) and a reference to the
bus, injected at construction via `set_memory_bus`:

```cython
cdef class MOS6502:
    cdef Registers _registers
    cdef Component _memory_bus            # typed — compile-time dispatch
    cdef object[:, :] _instruction_func   # precomputed [256][2] table
```

`_instruction_func` is a **precomputed dispatch table** built once at
construction time. Each entry holds a pair of `cdef` function pointers:
one for the addressing mode, one for the operation. `MOS6502.clock()`
reads the opcode at `PC`, looks up the two functions in the table, and
calls them — **no Python-level opcode dispatch, ever**, not even via a
big `if/elif` chain.

This design has two upsides:

1. Decode cost is essentially zero after the first cycle of each
   instruction.
2. Adding illegal opcodes (v0.2) or 65c02 opcodes (v0.3) is a matter of
   filling more table entries, not rewriting the dispatcher.

### 3.4 `Memory`, `TextDisplay`, `Font`

- **`Memory`** is a `Component` that wraps a contiguous
  `unsigned char[::1]` memoryview. `read_only` regions silently drop
  writes (matching real hardware ROM behavior).
- **`TextDisplay`** owns a character-grid framebuffer and a `Font`. It
  exposes `place_character(ch)`, `backspace()`, `clear_screen()`,
  `render_framebuffer()` (invoked once per UI frame by
  `System.sync_display` — flattens the index buffer + stamps the
  cursor), and `get_screen_buffer()` (a pure reference getter that
  returns the preallocated RGBA `array.array('f')` the sim owns). The
  frontend binds a DearPyGui raw texture to that buffer once at
  system-load time; per-frame GPU uploads are automatic and cost no
  Python-level copies. Peripherals that drive a text display (e.g.
  Apple I) embed one of these.
- **`Font`** loads a custom binary font format described in
  `graphics/textdisplay.pyx`. The format will be revisited alongside
  the font-maker tool in v0.3 (see [ROADMAP.md](ROADMAP.md)).

### 3.5 Peripherals

A "peripheral" is any `Component` subclass that represents real
hardware beyond plain memory. v0.1 ships `Apple1Display` and
`Apple1Keyboard` — the Apple I PIA is modelled as two independent
components on the bus, matching the real 6821 — and v0.2 adds NES PPU,
APU, controllers, and cartridge mappers.

Peripherals follow a small contract:

- **Must** override `cdef read(addr)` and `cdef write(addr, data)` for
  their register file.
- **May** override `cdef object get_framebuffer(self)` (defined on
  `Component`) returning a preallocated RGBA float buffer if they are
  a display device. `System.get_framebuffer()` calls through the
  base-class vtable. The returned buffer is owned by the peripheral
  and reused every frame — never allocate a fresh one per call. The
  per-frame refresh into that buffer happens in a sibling override,
  `cdef void render_framebuffer(self)`, which `System.sync_display`
  invokes at the end of every coarse frontend call. Splitting the two
  keeps `get_framebuffer` cheap (a pointer return) so the frontend
  can bind its DPG raw texture to the result once and forget about
  it.
- **May** override `cdef bint send_input(self, unsigned char)` and
  `cdef void clear_input(self)` for keyboard-like devices.
  `System.send_key()` / `System.clear_input_buffer()` call through the
  base-class vtable.
- **May** override `cdef void bind(self, object system)` to subscribe
  to cycle-accounting ticks via `system.register_tick_hook(self)`.
  `Apple1Display` uses this to hold DSP bit 7 busy for one full NTSC frame
  after a DSP write, without touching the CPU hot path.
- **Must not** own their own clock loop. `System` is the single owner
  of the clock — peripherals only see tick-hook fan-out, never a Python
  loop.

### 3.6 `System` — the orchestrator

`System` is the object the frontend holds onto. It's built from a
`SystemConfig` and owns every live component:

```cython
cdef class System:
    cdef MOS6502 _cpu
    cdef unsigned long _cpu_hz
    cdef dict _buses                      # str → BusController
    cdef Component _display               # direct ref, avoids string lookups
    cdef list _inputs                     # keyboard-likes, in declared order
    cdef dict _memory_regions             # str → Memory
    cdef tuple _memory_config             # MemoryRegion tuple, kept for runtime binary loads
```

Construction is described in detail in [SYSTEM_CONFIG.md §9](SYSTEM_CONFIG.md#9-how-system-builds-from-a-config).
In short: resolve CPU → build buses → wire memory → wire display → wire
inputs → wire audio/other → `bind()` every component → reset.

The **external API** is deliberately tiny:

```cython
cpdef void run_cycles(self, unsigned long master_cycles)
cpdef void run_for_microseconds(self, unsigned long microseconds)
cpdef unsigned long step_cycle(self)       # debug: advance one CPU clock cycle
cpdef unsigned long step_instruction(self) # debug: advance one full instruction
cpdef void reset(self)
cpdef void load_binary_at(self, unsigned int address, bytes data)
cpdef Registers get_registers(self)
cpdef void set_registers(self, Registers registers)
cpdef object get_framebuffer(self)
cpdef void sync_display(self)
cpdef void register_tick_hook(self, object component)
cpdef unsigned char peek(self, unsigned short address)
cpdef unsigned char poke(self, unsigned short address, unsigned char data)
cpdef bint is_mapped(self, unsigned short address)
cpdef void set_invalid_opcode_mode(self, unsigned char mode)
cpdef void set_unmapped_memory_mode(self, bint crash)
cpdef bint send_key(self, unsigned char char_)
cpdef void clear_input_buffer(self)
```

`step_cycle` and `step_instruction` are debug-only entry points — not
called on the continuous-run hot path. `step_cycle` delegates to
`run_cycles(1)`. `step_instruction` loops `run_cycles(1)` in Cython,
checking `get_registers()` between calls until the CPU loads a new
opcode (OPCODE_ADDR or OPCODE changes). Both return the number of
cycles consumed.

`sync_display` is the one-per-UI-frame chokepoint for the RGBA
flatten. `run_for_microseconds` / `step_cycle` / `step_instruction`
all call it on the way out so the frontend never has to; it's public
only so tests (and the initial-paint on system load) can force a
render without advancing cycles. The low-level `run_cycles` primitive
skips the sync on purpose — it runs inside `step_instruction`'s inner
loop and repeating the flatten there would be pure waste.

`peek`/`poke` forward to the `main` bus and exist for tests + debug
panels. The CPU hot path still calls the `cdef read`/`write` directly
through the Cython vtable — these helpers are a Python-visible
shortcut, not a detour on the clock path.

Everything else (debugger hooks, memory inspection, save states) is
layered on top of these primitives.

---

## 4. Clocking

### v0.1: single bus, 1:1 master → bus

```cython
cpdef void run_cycles(self, unsigned long master_cycles):
    if master_cycles:
        (<BusController>self._buses["main"]).run_cycles(master_cycles)

cpdef void run_for_microseconds(self, unsigned long microseconds):
    if microseconds:
        (<BusController>self._buses["main"]).run_for_microseconds(microseconds, self._cpu_hz)
```

The frontend calls `system.run_for_microseconds(16667)` once per UI
frame (60 Hz → 16.67 ms → 16667 µs → 16667 cycles at 1 MHz). That one
call executes thousands of 6502 cycles entirely in Cython.
`BusController.run_cycles(N)` fans out a single
`on_cycles_elapsed(N)` call per registered tick hook after the inner
loop — **not** once per cycle — so components that need cycle-accurate
timing (e.g. `Apple1Display`'s DSP busy bit) pay one C virtual call
per batch.

### v0.2: multi-bus with per-bus dividers

NES has two buses: the CPU bus (1.789 MHz) and the PPU bus (5.369 MHz —
3× CPU). `run_cycles(master)` will loop at the **master clock**
granularity and tick each bus according to its divider:

```cython
cpdef void run_cycles(self, unsigned long master_cycles):
    cdef unsigned long i
    for i in range(master_cycles):
        for bus_name, divider in self._bus_dividers.items():
            if i % divider == 0:
                self._buses[bus_name].clock()
```

The **external API does not change**. v0.1 configs that only declare a
`main` bus keep working; v0.2 NES configs add `buses.ppu` with a
divider. See [SYSTEM_CONFIG.md §3.3](SYSTEM_CONFIG.md#33-buses).

---

## 5. The frontend

### 5.1 `Py6502App`

The top-level DearPyGui shell. v0.1 scope is deliberately minimal. Its
responsibilities:

- Create the DearPyGui context, viewport, and menu bar on startup.
- Load the Apple I preset via `System.from_yaml_file(...)` and assign
  the result to `self.system`.
- Run a single per-frame loop that drains key presses via
  `self.system.send_key(char)`, calls
  `self.system.run_for_microseconds(16667)`, pushes the framebuffer
  into the DearPyGui texture, and then calls
  `dpg.render_dearpygui_frame()`.

**Everything inside that loop is an O(1) or O(N_on_screen) operation —
never O(cycles).**

### 5.2 System selector (planned)

The system-selector modal — a presets browser that reads
`py6502.sim.assets.presets/*.yaml`, lets the user pick one (and
eventually tweak its preset options via per-system configurators under
The system selector modal auto-discovers preset YAMLs from bundled
assets and supports user-loaded YAML configs. Settings are persisted to
`py6502_settings.json` alongside the DearPyGui layout file.

---

## 6. Data flow

### 6.1 Config load

```
apple_i.yaml
       │
       │ yaml.safe_load
       ▼
  dict[str, Any]
       │
       │ validate + resolve URIs
       ▼
  SystemConfig (frozen dataclass)
       │
       │ System(config)
       ▼
  Live System object
```

### 6.2 Per-frame tick (UI thread)

```
Py6502App.run() — DearPyGui frame loop
       │
       ▼
  emulator.on_update():
       │
       ├── drain UI key buffer → input device.add_character_to_kb_buffer()
       │
       ├── system.run_for_microseconds(16667)
       │       │
       │       ├── BusController.run_cycles(16667)
       │       │       │
       │       │       ▼
       │       │   for _ in 16667: MOS6502.clock()
       │       │       │
       │       │       ▼
       │       │   each clock reads/writes bus → component.read/write (cdef)
       │       │
       │       └── sync_display()  → display.render_framebuffer()
       │               (cursor blink + index→RGBA flatten into the
       │                raw-texture-bound buffer)
       │
       └── (the framebuffer is already up to date; no Python-level
            upload needed here — the DPG raw texture is bound to it)
       │
       ▼
  dpg.render_dearpygui_frame()   # DPG re-uploads the bound buffer to the GPU
```

### 6.3 Read cycle inside the CPU

```
MOS6502.clock()  (Cython)
       │
       │ opcode = self._memory_bus.read(PC)
       ▼
BusController.read(addr)  (Cython, @boundscheck(False))
       │
       │ mapped = self._component_address_map[addr]
       ▼
Component.read(mapped.internal_address)  (cdef virtual call)
       │
       ▼
 returns byte
```

Zero Python calls. This path is hit millions of times per second.

---

## 7. Performance philosophy

The detailed rules live in
[src/py6502/sim/CLAUDE.md](../src/py6502/sim/CLAUDE.md). The short
version:

1. **No Python loops in steady state.** If it runs once per cycle or
   once per frame for every pixel, it's in `cdef` code.
2. **No allocations on the hot path.** Buffers are allocated once at
   init and reused. That includes framebuffers, key buffers, and
   decode state.
3. **Direct dispatch, not dynamic dispatch.** Precomputed tables
   (instruction dispatch, mapped address table) beat hash lookups every
   time.
4. **Coarse APIs at boundaries.** One `run_for_microseconds` call per
   frame, not one `clock()` call per cycle from Python.
5. **Measure, don't guess.** The functional-test stress runner reports
   cycles/sec — any PR that regresses it is suspect.

---

## 8. Testing strategy

Detailed in the test plan (see
[ROADMAP.md](ROADMAP.md)). The architectural summary:

- **Unit tests** under `tests/` cover the `System` build pipeline end
  to end: config loader (`test_system_loader.py`,
  `test_system_smoke.py`), validation rules (`test_options.py`,
  `test_binaries.py`), config writer round-trip (`test_writer.py`),
  asset manifest (`test_manifest.py`), per-user config paths
  (`test_paths.py`), runtime binary loading
  (`test_runtime_load_binary.py`), Apple I region split
  (`test_apple1_split.py`), and the strict-mode error paths for
  invalid opcodes (`test_invalid_opcode.py`) and unmapped memory
  (`test_unmapped_memory.py`).
- **Klaus 6502 functional tests** and **Bruce Clark decimal tests**
  are deferred to v0.3 (see issue
  [#50](https://github.com/ricky-groenewald/py6502/issues/50)). The
  upstream binaries are GPL-3.0, so the v0.3 plan fetches them at CI
  time rather than vendoring them in the wheel; thin runners under
  `scripts/` will invoke them once that lands.
- A **performance regression test** whose entire job is to fail loudly
  if a Python loop sneaks back into the hot path is on the v0.1 punch
  list and will land alongside the Klaus harness in v0.3 (it needs the
  Klaus binary as its representative workload).

---

## 9. What's deliberately *not* here

- **Persistence / save states.** No plan for v0.1; v0.3 target.
- **Netplay, rewind, TAS.** Out of scope entirely.
- **Dynamic component reloading.** Once `System` is built, its topology
  is frozen. Changing machines means destroying the `System` and
  building a new one.
- **Threading.** The simulator is strictly single-threaded. The UI
  thread is the clock owner. Audio in v0.2 may introduce a producer/
  consumer ring buffer but will not introduce multithreaded
  *simulation*.
- **A general-purpose 6502 debugger protocol.** The `get_registers` /
  `set_registers` / memory-peek primitives are enough for v0.1's
  in-process debug panels; remote debugger work is v0.3+.

---

## 10. For a deeper dive

- [SYSTEM_CONFIG.md](SYSTEM_CONFIG.md) — the declarative config
  contract, registry, validation rules, and how `System` interprets a
  config at build time.
- [ROADMAP.md](ROADMAP.md) — milestones, open issues, and the
  narrative of what's being built when.
- [src/py6502/sim/CLAUDE.md](../src/py6502/sim/CLAUDE.md) — the
  non-negotiable performance rules, Cython conventions, and gotchas
  when touching `.pyx`/`.pxd` files.
- [src/py6502/ui/CLAUDE.md](../src/py6502/ui/CLAUDE.md) — DearPyGui
  conventions, frame-loop contract, and UI-side gotchas.
