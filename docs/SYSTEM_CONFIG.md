# System Config Specification

> **Status:** v0.1 draft — this is the contract end-users write to when
> describing a machine for py6502 to emulate. It also defines the internal
> dataclasses that `py6502.sim.system.System` consumes.
>
> **Audience:** end-users authoring custom configs, contributors writing
> preset configs, and future maintainers extending the schema for v0.2+.

A "system config" is a **YAML file** that declaratively describes a 6502-era
machine: its CPU, memory regions, and peripherals. py6502 loads a config,
validates it, resolves component types through a registry, and builds a
live `System` object that's ready to run.

Configs are **pure data**. They never contain executable code. This makes
them safe to share between users, easy to diff and version, and trivial to
generate from a UI.

---

## 1. Design principles

1. **Pure data, not code.** YAML only. No Python files masquerading as
   configs. Sharing a config means sharing a `.yaml` (plus any referenced
   `.bin` files) — never executable code.
2. **Component types are resolved through a registry.** The YAML references
   components by name (`"Apple1Display"`), and a Python-side registry maps
   those names to the actual Cython classes. Users can only instantiate
   components py6502 has explicitly registered.
3. **ROM data lives in external files, never inline.** Configs stay
   human-readable; ROMs stay binary. See [§4 Source URIs](#4-source-uris).
4. **Typed externally, flat internally.** The schema has distinct
   `display` / `inputs` / `audio` / `other` sections so configs are
   self-documenting and the UI has clean hooks; internally `System`
   flattens everything into a single component iteration.
5. **Forward-compatible with multi-bus.** v0.1 machines use a single
   implicit bus called `main`. v0.2 (NES) adds a second bus without
   breaking v0.1 configs.
6. **Strict validation with clear errors.** Unknown fields fail the load.
   Unknown component types fail with the registry's available list.
   Overlapping address ranges fail with the conflicting regions named.

---

## 2. File format at a glance

Minimal Apple I config:

```yaml
version: 1
id: apple_i
name: Apple I
description: The original Apple I from 1976.

cpu:
  type: MOS6502
  hz: 1000000

memory:
  - name: RAM
    start: 0x0000
    size: 0x1000
  - name: ROM
    start: 0xFF00
    size: 0x0100
    read_only: true
    source: resource:py6502.sim.assets.bios/apple1-wozmon.bin

display:
  type: Apple1Display
  address: 0xD012

inputs:
  - type: Apple1Keyboard
    address: 0xD010
```

That's the whole file. Everything else is optional. py6502 fills in
defaults for `buses`, `audio`, `other`, `author`, `tags`, and each
component's `bus` field.

---

## 3. Schema reference

### 3.1 Top-level fields

| Field         | Type             | Required | Default | Description                                                               |
|---------------|------------------|----------|---------|---------------------------------------------------------------------------|
| `version`     | int              | yes      | —       | Schema version. Currently `1`. Validator rejects unknown versions.        |
| `id`          | string           | yes      | —       | Stable identifier. Must match `[a-z0-9_]+`. Used for filenames + CLI.     |
| `name`        | string           | yes      | —       | Human-readable name shown in the UI.                                      |
| `description` | string           | yes      | —       | One-paragraph description. Multi-line allowed via YAML `|`.               |
| `cpu`         | CpuSpec          | yes      | —       | See [§3.2](#32-cpu).                                                      |
| `memory`      | list[MemRegion]  | yes      | —       | At least one region. See [§3.4](#34-memory).                              |
| `display`     | ComponentSpec    | no       | `null`  | Exactly one display device or none. See [§3.5](#35-display).              |
| `inputs`      | list[CompSpec]   | no       | `[]`    | Zero or more input devices. See [§3.6](#36-inputs).                       |
| `audio`       | ComponentSpec    | no       | `null`  | Exactly one audio device or none. (v0.2)                                  |
| `other`       | list[CompSpec]   | no       | `[]`    | Misc components (timers, RTCs, etc.).                                     |
| `buses`       | dict[str,BusSpec]| no       | see §3.3| Bus topology. v0.1 defaults to a single `main` bus.                       |
| `author`      | string           | no       | `null`  | Credit field for user-shared configs.                                     |
| `tags`        | list[string]     | no       | `[]`    | Free-form tags for UI filtering.                                          |

### 3.2 `cpu`

```yaml
cpu:
  type: MOS6502       # required, must exist in COMPONENT_REGISTRY
  hz: 1000000         # required, master clock in Hz (integer, > 0)
```

The CPU type string resolves through the same registry as components
([§5](#5-the-component-registry)). `hz` is the **master clock** —
per-bus dividers are applied on top of this in v0.2.

v0.1 registered CPU types:

- `MOS6502` — the standard 6502.

v0.2+ (planned): `R2A03` (NES — 6502 minus BCD mode), `W65C02S`.

### 3.3 `buses`

v0.1 configs usually omit this block. It exists to be forward-compatible
with v0.2 multi-bus machines.

```yaml
buses:
  main:
    address_width: 16      # optional, default 16
```

If omitted, py6502 synthesizes `{main: {address_width: 16}}`. Component
specs reference a bus by name via their optional `bus` field.

v0.2 NES example:

```yaml
buses:
  main:
    address_width: 16
  ppu:
    address_width: 14
    divider: 3             # PPU runs 3x CPU clock (forward-compat, not v0.1)
```

**Validator constraint (v0.1):** only `main` is allowed. Any other bus
name fails validation with `Bus 'X' is not supported in schema version 1`.

### 3.4 `memory`

A list of `MemoryRegion` entries. At least one is required.

```yaml
memory:
  - name: RAM               # required, unique within the config
    start: 0x0000           # required, base address on the bus
    size: 0x1000            # required, bytes (int or hex literal)
    read_only: false        # optional, default false
    bus: main               # optional, default "main"
    source: null            # optional, default null → zero-initialized
    load_offset: 0          # optional, where in the region to load `source`
```

**Fields:**

| Field         | Type   | Required | Default  | Notes                                                                 |
|---------------|--------|----------|----------|-----------------------------------------------------------------------|
| `name`        | string | yes      | —        | Must be unique within this config. Referenced by `load_binary`.       |
| `start`       | int    | yes      | —        | Bus address where the region begins. Hex literals (`0x0000`) allowed. |
| `size`        | int    | yes      | —        | Number of bytes. Must satisfy `start + size <= 2**address_width`.     |
| `read_only`   | bool   | no       | `false`  | If `true`, writes are silently dropped (ROM semantics).               |
| `bus`         | string | no       | `"main"` | Which bus the region sits on.                                         |
| `source`      | URI    | no       | `null`   | See [§4 Source URIs](#4-source-uris). `null` → zero-initialized.      |
| `load_offset` | int    | no       | `0`      | Byte offset within the region where `source` bytes start loading.     |

**Validation:**

- Region names must be unique within a config.
- Regions on the same bus must not overlap.
- `start` must be bus-aligned to a byte boundary (implicit — addresses
  are bytes).
- If `source` is provided, the source file must fit inside `size -
  load_offset`; excess bytes fail the load.

### 3.5 `display`

Zero or one display device. Omitting `display:` produces a headless
system with no framebuffer.

```yaml
display:
  type: Apple1Display       # required, resolved via component registry
  address: 0xD012           # required, base address on the bus
  bus: main                 # optional, default "main"
  params:                   # optional, type-specific kwargs passed to ctor
    native_size: [240, 192]
```

**Fields:**

| Field     | Type              | Required | Default  | Notes                                               |
|-----------|-------------------|----------|----------|-----------------------------------------------------|
| `type`    | string            | yes      | —        | Must exist in `COMPONENT_REGISTRY`.                 |
| `address` | int               | yes      | —        | Base bus address of the component's register file. |
| `bus`     | string            | no       | `"main"` | Which bus the component sits on.                   |
| `params`  | dict[str, Any]    | no       | `{}`     | Type-specific keyword arguments.                   |

**Contract:** a display component must expose a `get_framebuffer()`
method returning an RGBA buffer of its native dimensions. `System` keeps
a direct reference to it so `System.get_framebuffer()` never needs a
string lookup.

### 3.6 `inputs`

A list of input devices. Same shape as `display`, just a list:

```yaml
inputs:
  - type: Apple1Keyboard
    address: 0xD010
  - type: NESController
    address: 0x4016
    params:
      player: 1
```

### 3.7 `audio` and `other`

Same shape. `audio` is singular (at most one device per system).
`other` is a list for miscellaneous components (cartridge mappers,
timers, RTCs, anything that's not display/input/audio).

v0.1 doesn't use either; they exist for forward-compatibility with v0.2.

---

## 4. Source URIs

The `source:` field on a memory region is a **URI string** with one of
two schemes:

### `resource:`

Loads bytes from a package resource bundled inside py6502.

```
resource:py6502.sim.assets.bios/apple1-wozmon.bin
```

Grammar: `resource:<python_package>/<filename>`. The package must be
importable (normally one of `py6502.sim.assets.*`). Intended for
**preset configs** that ship with py6502.

### `file:`

Loads bytes from a local file.

```
file:./roms/my_custom.bin
file:/absolute/path/to/rom.bin
```

Relative paths are resolved **relative to the config file's directory**,
not the working directory. This makes shared config bundles portable —
a user can zip a `.yaml` + its `.bin` siblings and hand it to someone
else.

**No other schemes are supported.** There is no `http:` or `https:` —
configs must never trigger network fetches at load time. Security
boundary is local filesystem only.

---

## 5. The component registry

The registry is a plain dict on the Python side:

```python
# src/py6502/sim/system/registry.py
from py6502.sim.bus import Memory, Component
from py6502.sim.cpu.mos6502 import MOS6502
from py6502.sim.peripherals import Apple1Display, Apple1Keyboard

COMPONENT_REGISTRY: dict[str, type] = {
    # CPUs
    "MOS6502":        MOS6502,
    # Memory — built-in primitive, always available
    "Memory":         Memory,
    # Apple I
    "Apple1Display":  Apple1Display,
    "Apple1Keyboard": Apple1Keyboard,
}

def resolve(name: str) -> type:
    if name not in COMPONENT_REGISTRY:
        available = ", ".join(sorted(COMPONENT_REGISTRY))
        raise ValueError(
            f"Unknown component type {name!r}. Available: {available}"
        )
    return COMPONENT_REGISTRY[name]
```

**Why a registry:**

1. **Security.** Users can only instantiate types py6502 has explicitly
   registered. A shared config can't ship a type that imports
   `subprocess` or runs arbitrary code.
2. **Fast, clear errors.** Load a config referencing an unregistered
   type and you get the available list in the error message.
3. **Discoverability.** The registry is the canonical "what does py6502
   know about?" list. The `/new-system` skill reads from it; the UI
   populates dropdowns from it; this doc lists it.
4. **Decoupling.** YAML doesn't know about Python imports. The registry
   is the only place that does.

New components register themselves **once**, in `registry.py`, after
their class is defined. There is no decorator magic — imports alone do
not register.

---

## 6. Presets vs user configs

py6502 distinguishes two kinds of configs:

**Preset configs** ship inside the py6502 package at
`src/py6502/sim/assets/configs/*.yaml`. They use `resource:` URIs for
all binary data so the user never has to supply their own files. The
`New System` dialog loads presets by scanning this directory.

**User configs** live anywhere on the user's filesystem. They use
`file:` URIs (resolved relative to the config file's directory) for
binary data. The `New System` dialog exposes "Load config from file…"
to pick one.

A user can save a preset + their custom edits as a new user config.

### v0.1 preset list

- `apple_i_4k.yaml` — original 4K Apple I with wozmon
- `apple_i_8k.yaml` — 8K variant
- `custom_6502.yaml` — bare-bones configurable starting point

---

## 7. Validation rules

The loader runs these checks in order. The **first** failing rule fails
the load with a clear error message pointing at the offending line.

1. **Schema version.** Must be `1`. Unknown versions fail with a list of
   supported versions.
2. **Required fields.** All fields marked *required* in §3 must be
   present.
3. **No unknown fields.** Extra keys fail the load — they're almost
   always typos.
4. **Component types exist.** Every `type:` string must exist in
   `COMPONENT_REGISTRY`. Failure message lists available types.
5. **Memory region names are unique** within the config.
6. **Memory regions don't overlap** on the same bus.
7. **Component addresses don't overlap** memory regions or each other on
   the same bus.
8. **Addresses fit the bus.** `start + size <= 2**address_width`.
9. **`buses` constraints.** v0.1 only accepts `main`.
10. **Source URIs resolve.** `resource:` packages must be importable;
    `file:` paths (relative to the config's dir) must exist.
11. **Source size fits.** For each memory region with a `source`, the
    source file size must be `<= region.size - load_offset`.

Validation failures raise `py6502.sim.system.ConfigError` with a message
of the form:

```
ConfigError: apple_i.yaml:12: memory region 'RAM' overlaps with 'ROM' on bus 'main'
    RAM:  0x0000..0x1FFF
    ROM:  0x1800..0x1FFF
```

---

## 8. Internal representation

After loading and validating, py6502 converts the YAML into a set of
**frozen dataclasses** defined in `py6502.sim.system.config`:

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class CpuSpec:
    type: str           # must exist in COMPONENT_REGISTRY
    hz: int

@dataclass(frozen=True)
class BusSpec:
    address_width: int = 16

@dataclass(frozen=True)
class MemoryRegion:
    name: str
    start: int
    size: int
    read_only: bool = False
    bus: str = "main"
    source: Optional[str] = None        # raw URI string
    load_offset: int = 0

@dataclass(frozen=True)
class ComponentSpec:
    type: str                           # must exist in COMPONENT_REGISTRY
    address: int
    bus: str = "main"
    params: dict = field(default_factory=dict)

@dataclass(frozen=True)
class SystemConfig:
    version: int
    id: str
    name: str
    description: str
    cpu: CpuSpec
    memory: tuple[MemoryRegion, ...]
    buses: dict[str, BusSpec] = field(default_factory=lambda: {"main": BusSpec()})
    display: Optional[ComponentSpec] = None
    inputs: tuple[ComponentSpec, ...] = ()
    audio: Optional[ComponentSpec] = None
    other: tuple[ComponentSpec, ...] = ()
    author: Optional[str] = None
    tags: tuple[str, ...] = ()

    @classmethod
    def from_yaml_file(cls, path: Path) -> "SystemConfig": ...

    @classmethod
    def from_yaml_text(cls, text: str, base_dir: Path) -> "SystemConfig": ...
```

Dataclasses are frozen so they can be safely shared, hashed, and used as
cache keys. `list` fields become `tuple`s in the dataclass form for the
same reason.

---

## 9. How `System` builds from a config

`System.__init__(config: SystemConfig)` does the following, in order:

1. **Resolve the CPU.** `COMPONENT_REGISTRY[config.cpu.type]()`, store
   as `self._cpu`, stash `self._cpu_hz`.
2. **Build buses.** For each entry in `config.buses`, create a
   `BusController` and store it in `self._buses[name]`. Inject the CPU
   into the `main` bus.
3. **Wire memory regions.** For each `MemoryRegion`: create a `Memory`
   component of the right size and read-only flag, load bytes from the
   `source` URI if present (respecting `load_offset`), and call
   `self._buses[region.bus].add_component(mem, region.start)`.
4. **Wire peripherals.** Flatten `display` + `inputs` + `audio` +
   `other` into one internal list. For each spec: resolve the type via
   the registry, instantiate with `(bus_controller, **spec.params)`,
   and call `self._buses[spec.bus].add_component(periph, spec.address)`.
   Keep a **direct reference** to the `display` device in
   `self._display` so `get_framebuffer()` never does a lookup.
5. **Reset.** Call `self._buses["main"].send_reset()`.

### Clocking

`System` owns the clock loop. Peripherals do **not** drive their own
clock anymore:

```cython
cpdef void run_cycles(self, unsigned long master_cycles):
    # v0.1: single bus, 1:1 master → bus
    self._buses["main"].run_cycles(master_cycles)

cpdef void run_for_microseconds(self, unsigned long microseconds):
    cdef unsigned long cycles = (microseconds * self._cpu_hz) // 1000000
    if cycles:
        self.run_cycles(cycles)
```

v0.2 introduces per-bus dividers so the PPU bus runs 3× the CPU bus off
a single master cycle count. The external API doesn't change.

---

## 10. Versioning and forward-compatibility

The `version:` field at the top of every config is the schema version.

**Rules for bumping:**

- **Additive changes** (new optional fields, new component types, new
  `buses` entries) → same version. v0.1 loaders must accept them by
  ignoring unknown *optional* fields cleanly. The v0.1 validator does
  not do this today (strict mode); the intent is to relax this *only*
  when a future additive-compat field is added.
- **Breaking changes** (renaming a field, changing semantics, removing
  support) → new version number. The loader refuses to load old
  versions unless a migration path is provided.

**v0.2 additions that will bump the version to `2`:**

- Multi-bus support (`buses:` with non-`main` entries)
- Per-bus clock dividers
- Mirrored address mappings (`mirror:` on components)
- CPU variants (`R2A03`, `W65C02S`)

---

## 11. Future extensions

These are documented here so the v0.1 implementation doesn't paint us
into a corner:

- **Mirroring.** v0.2 adds `mirror: {stride: N, count: M}` as an
  optional field on component specs. The flatten step in `System`
  decomposes this into `M` calls to `BusController.add_component`.
- **Non-contiguous address maps.** Rare but useful. v0.3 may add
  `address_ranges: [[start, size], ...]` for components with
  non-contiguous register files. No use case in v0.1 or v0.2.
- **Cartridge mappers.** NES mappers are stateful address translators
  that swap memory regions at runtime. They'll live in `other:` and
  implement a `bank_switch(slot, bank)` contract. v0.2 work.
- **Multiple displays.** Rare but possible (e.g., a machine with a
  character LCD *and* a framebuffer). If needed, `display` becomes
  `displays: list[ComponentSpec]` with a schema version bump.
- **Save states.** Serialization of a running `System` back to something
  roughly config-shaped, with a `state:` block capturing RAM, registers,
  and per-peripheral state. v0.3 work.
- **Font-maker tool output.** When the v0.3 font-maker ships, custom
  font files can be referenced from display component `params:` via
  `file:` URIs.

---

## Appendix: full Apple I preset

The canonical preset shipped with py6502. Annotated for clarity.

```yaml
version: 1
id: apple_i_4k
name: Apple I (4K)
description: |
  The original Apple I from 1976: 1 MHz 6502, 4 KiB RAM, Apple I cassette
  interface I/O chip at $D010-$D013, and Steve Wozniak's monitor program
  (wozmon) in ROM at $FF00-$FFFF.
author: py6502
tags: [apple, 1976, homebrew]

cpu:
  type: MOS6502
  hz: 1000000           # 1 MHz

memory:
  - name: RAM
    start: 0x0000
    size: 0x1000        # 4 KiB

  - name: ROM
    start: 0xFF00
    size: 0x0100        # 256 bytes
    read_only: true
    source: resource:py6502.sim.assets.bios/apple1-wozmon.bin

display:
  type: Apple1Display
  address: 0xD012       # DSP + DSPCR
  params:
    native_size: [240, 192]    # 40 cols x 24 rows of 6x8 glyphs

inputs:
  - type: Apple1Keyboard
    address: 0xD010     # KBD + KBDCR
```

The 8K variant (`apple_i_8k.yaml`) differs only in
`memory[0].size: 0x2000`. Everything else is identical.
