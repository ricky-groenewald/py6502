# Roadmap

This is the narrative view of where `py6502` is going. The canonical source of
truth for what is actually scheduled is the
[GitHub milestones](https://github.com/ricky-groenewald/py6502/milestones)
page — this document exists to give the milestones context and to record the
design decisions that shaped them.

The tagline is **"Emulator of everything 6502"**: a free, hobbyist-friendly
platform for emulating real 6502-era machines and for building new ones on
the same substrate. The source is public under the PolyForm
Noncommercial License 1.0.0: free to use, change, and share for
personal, educational, research, and non-profit purposes; commercial
use is not permitted (see `LICENSE` and `NOTICE`). Each milestone below
adds one big capability to the platform.

---

## Milestones at a glance

| Release | Theme                        | Scope in one line                                  |
| ------- | ---------------------------- | -------------------------------------------------- |
| v0.1    | First 6502 release           | Cycle-accurate 6502, Apple I, new UI shell, tests. |
| v0.2    | Famicom / NES release        | Multi-bus clocking, PPU, APU, cartridges, input.   |
| v0.3    | Development Tools            | Assembler, editors, snippet workflow, 65C02.       |

Each milestone is considered "done" when its GitHub milestone is closed and a
versioned tag is cut on `main`.

---

## v0.1 — First 6502 release

**Goal.** A single, coherent release that proves the core substrate works:
a cycle-accurate 6502, a flat 64K bus, IaC system configs, a reusable
`System` façade, a DearPyGui shell that can boot and interact with an Apple I,
and a pytest harness wired up to CI.

**Why it matters.** Everything from v0.2 onward depends on this substrate. If
the clocking model, the IaC config format, or the peripheral base class is
wrong here, every later release pays for it.

**Scope.**

- Finish the `py6502.sim.system` rewrite against `docs/SYSTEM_CONFIG.md`.
  Drop `Apple1.clock()`'s internal 16667-cycle loop; the loop lives in
  `System.run_cycles` / `run_for_microseconds`. See `docs/ARCHITECTURE.md`.
- Abstract display + input peripherals so the Apple I is a *user* of those
  abstractions, not a special case in `System.get_framebuffer`.
- Pytest fixtures + a performance regression test that fails loudly if a
  Python loop sneaks back into a hot path. The Klaus Dormann functional and
  Bruce Clark decimal conformance suites moved to v0.2 (see
  [#50](https://github.com/ricky-groenewald/py6502/issues/50)): the
  upstream GPL-3.0 binaries are fetched at run time instead of bundled as
  sim assets. The performance regression test itself is
  [#79](https://github.com/ricky-groenewald/py6502/issues/79).
- GitHub Actions CI that builds the Cython extensions and runs the full
  pytest suite (with `@pytest.mark.slow` for the Klaus runs).
- Fix undefined-behaviour on invalid opcodes / unmapped memory accesses.
- Finalise the `Py6502App` UI shell with disassembly panel, register
  view, memory monitor, and binary loader.
- Documentation: README + per-package READMEs, in-source comments on the 6502
  core.

**Open issues in GitHub milestone "v0.1 Release - First 6502 release":**

_None — milestone closed._

**Explicit non-goals for v0.1.**

- No PPU, no sprites, no audio, no controllers.
- No multi-bus clocking with divisors (see v0.2).
- No assembler, no editors, no snippet manager (see v0.3).
- No illegal / undocumented 6502 opcodes (see v0.2).
- No 65C02 (see v0.3).

---

## v0.2 — Famicom / NES release

**Goal.** Boot a real NES ROM to a playable state. This is the milestone
that turns `py6502` from "a nice 6502 demo" into an actual retro-console
emulator, and it's also where the architecture has to grow up.

**The architectural shift.** v0.1 assumes a single `main` bus ticked at one
frequency. The NES has a CPU bus *and* a PPU bus running at a 3× divider
off the master clock, plus an APU on the CPU side. `SystemConfig.buses` is
already a `dict[str, BusSpec]` for exactly this reason (see
`docs/SYSTEM_CONFIG.md` §buses), but the clocking model itself has to become
divider-aware before it's useful. The shape is settled: see the
foundation bullets below and `docs/ARCHITECTURE.md` §4.

**Scope.**

- **Bus refactor foundation**, in order: a hot-path guard test and a
  recorded throughput baseline
  ([#79](https://github.com/ricky-groenewald/py6502/issues/79)); move the
  cycle loop from `BusController` into `System`
  ([#80](https://github.com/ricky-groenewald/py6502/issues/80)); an
  address mask, `remove_component`, and a `mirrors` count on `Memory`
  ([#81](https://github.com/ricky-groenewald/py6502/issues/81)); schema
  version 2 with `master_hz`, a `processors` list, component ids, and
  `mirrors` ([#82](https://github.com/ricky-groenewald/py6502/issues/82));
  cross-component lookup plus `bind` and `reset` fan-out to every
  component ([#83](https://github.com/ricky-groenewald/py6502/issues/83));
  and a CPU interrupt line model
  ([#84](https://github.com/ricky-groenewald/py6502/issues/84)). The
  Apple I stays bit-identical throughout.
- Variable timing / multi-unit clock model
  ([#27](https://github.com/ricky-groenewald/py6502/issues/27)). `System`
  owns the master clock and steps each processing unit at its divider,
  iterating the fastest unit with integer accumulators for the rest. No
  Python loops in steady state — this is the most load-bearing
  performance change in v0.2.
- A `PPU` component (background, sprites, tile/character map rendering). The
  PPU does *not* reuse `TextDisplay`; it is a first-class graphics peripheral
  that produces its own framebuffer.
- An `APU` component and a frontend audio sink.
- NES controller input as a proper input peripheral.
- Cartridge loader + mapper support (start with NROM / MMC1 / UxROM — the
  minimum to run the well-known test carts and small homebrew games).
- Illegal / undocumented 6502 opcodes — **done** in
  [#78](https://github.com/ricky-groenewald/py6502/pull/78). The UI
  toggle and disassembler mnemonics follow in
  [#85](https://github.com/ricky-groenewald/py6502/issues/85).
- Save states ([#75](https://github.com/ricky-groenewald/py6502/issues/75)):
  snapshot and restore of every component's state. NES-primary but not
  NES-only.
- A short note on the CPU core's cycle state machine
  ([#86](https://github.com/ricky-groenewald/py6502/issues/86)) so CPU
  work such as the dummy-read audit
  ([#77](https://github.com/ricky-groenewald/py6502/issues/77)) has a
  primary reference in the repo.
- **Multiprocessing sim/frontend split.** Move the simulator into its own OS
  process so the DearPyGui (or successor) frontend no longer shares a GIL
  with the sim tick loop. The one-coarse-call-per-frame contract already
  isolates the two; this is a mechanical refactor behind a stable `System`
  API, with `multiprocessing.shared_memory` framebuffer ping-pong falling
  out for free. Sequenced after the variable-clock work, since the
  master-clock shape needs to be stable before it's worth crossing a
  process boundary.
- **Frontend library re-evaluation.** DearPyGui currently requires a local
  source edit to disable linear texture filtering — a smell, not yet a
  rewrite justification. Before v0.2 ships, evaluate upstreaming the fix,
  switching to `pyimgui`, or dropping ImGui entirely in favour of a thin
  raylib / pyglet / SDL2 setup. Writing a custom Dear ImGui binding from
  scratch is explicitly *not* on the list.
- Conformance and CI: Klaus Dormann and Bruce Clark runners under
  `scripts/` with run-time fetch of the GPL-3.0 binaries
  ([#50](https://github.com/ricky-groenewald/py6502/issues/50)), and a
  GitHub Actions workflow that builds the extensions and runs pytest plus
  the runners ([#4](https://github.com/ricky-groenewald/py6502/issues/4)).
  Coverage grows to the PPU, mappers, and multi-unit clocking as they
  land; nestest ([#73](https://github.com/ricky-groenewald/py6502/issues/73))
  joins the same harness.

**Open issues in GitHub milestone "v0.2 Release - Famicom / NES release":**

- [#2](https://github.com/ricky-groenewald/py6502/issues/2) — 6502: Create tests
- [#4](https://github.com/ricky-groenewald/py6502/issues/4) — Github actions: Automated testing upon pushing / PR / etc.
- [#12](https://github.com/ricky-groenewald/py6502/issues/12) — NES Emulation
- [#13](https://github.com/ricky-groenewald/py6502/issues/13) — Cartridge Loading / Mappers
- [#14](https://github.com/ricky-groenewald/py6502/issues/14) — Character / Tile map display
- [#15](https://github.com/ricky-groenewald/py6502/issues/15) — Background Display
- [#16](https://github.com/ricky-groenewald/py6502/issues/16) — Sprites Display
- [#17](https://github.com/ricky-groenewald/py6502/issues/17) — Controller Input
- [#18](https://github.com/ricky-groenewald/py6502/issues/18) — Audio
- [#27](https://github.com/ricky-groenewald/py6502/issues/27) — Variable Timing/Clock Model
- [#32](https://github.com/ricky-groenewald/py6502/issues/32) — Multiprocessing sim/frontend split
- [#33](https://github.com/ricky-groenewald/py6502/issues/33) — Frontend library re-evaluation (DearPyGui friction)
- [#40](https://github.com/ricky-groenewald/py6502/issues/40) — Create Input / Display abstracts
- [#50](https://github.com/ricky-groenewald/py6502/issues/50) — Wire Klaus + Bruce Clark tests into pytest with perf reporting
- [#62](https://github.com/ricky-groenewald/py6502/issues/62) — [BUG] BusController corrupts bus snapshot on debug peek — add peek/poke bypass
- [#63](https://github.com/ricky-groenewald/py6502/issues/63) — Gate debug-monitor refresh to pause/step events
- [#64](https://github.com/ricky-groenewald/py6502/issues/64) — v0.2 dedup + dead-code + doc-drift cleanup pass
- [#65](https://github.com/ricky-groenewald/py6502/issues/65) — v0.2 performance audit + baseline
- [#66](https://github.com/ricky-groenewald/py6502/issues/66) — R2A03 CPU variant (no-BCD + OAM/DMC DMA stall)
- [#67](https://github.com/ricky-groenewald/py6502/issues/67) — NMI / IRQ wiring for NES peripherals
- [#68](https://github.com/ricky-groenewald/py6502/issues/68) — PPU bus: VRAM, nametable mirroring, palette RAM
- [#69](https://github.com/ricky-groenewald/py6502/issues/69) — PixelDisplay graphics primitive (bitmap framebuffer)
- [#70](https://github.com/ricky-groenewald/py6502/issues/70) — PPU register window on main bus ($2000-$3FFF)
- [#71](https://github.com/ricky-groenewald/py6502/issues/71) — Mapper component contract (runtime bank-switching shape)
- [#72](https://github.com/ricky-groenewald/py6502/issues/72) — Bundled NES preset(s) + asset manifest entry
- [#73](https://github.com/ricky-groenewald/py6502/issues/73) — nestest CPU conformance runner in CI
- [#74](https://github.com/ricky-groenewald/py6502/issues/74) — PAL NES sim-side support
- [#75](https://github.com/ricky-groenewald/py6502/issues/75) — Save states (snapshot + restore emulator state)
- [#77](https://github.com/ricky-groenewald/py6502/issues/77) — Audit indexed-addressing dummy-read addresses across all opcode families
- [#79](https://github.com/ricky-groenewald/py6502/issues/79) — Hot-path Python-call guard test and v0.1 performance baseline
- [#80](https://github.com/ricky-groenewald/py6502/issues/80) — Decouple the cycle pump from BusController into System
- [#81](https://github.com/ricky-groenewald/py6502/issues/81) — BusController address mask, remove_component, and Memory mirrors
- [#82](https://github.com/ricky-groenewald/py6502/issues/82) — Schema version 2: master clock, processors list, component ids, mirrors field
- [#83](https://github.com/ricky-groenewald/py6502/issues/83) — Cross-component references and lifecycle fan-out
- [#84](https://github.com/ricky-groenewald/py6502/issues/84) — CPU input lines: IRQ, NMI, and RDY
- [#85](https://github.com/ricky-groenewald/py6502/issues/85) — Expose illegal-opcode mode in the UI
- [#86](https://github.com/ricky-groenewald/py6502/issues/86) — Document the MOS6502 cycle state machine
- [#89](https://github.com/ricky-groenewald/py6502/issues/89) — Config errors carry file name and line number
- [#90](https://github.com/ricky-groenewald/py6502/issues/90) — NES I/O register window component ($4000-$401F)

#2 and #4 are "v0.1 foundation" issues that live in the v0.2 milestone only
because pytest/CI work will grow substantially as NES features land. The
fixture scaffolding itself ships in v0.1; v0.2 expands it.

---

## v0.3 — Development Tools

**Goal.** Make `py6502` the environment you reach for when you want to
*build* something for a 6502 machine, not just run one. This is where the
"hobbyist-friendly platform" framing earns its keep.

**Scope.**

- A real in-process assembler (the old one was removed in
  [#28](https://github.com/ricky-groenewald/py6502/issues/28); the
  replacement will be built against the `System` API, not the pre-restructure
  bus-level API).
- An integrated editor for code snippets, with save/load.
- A character-map / sprite editor. This is the natural home for the font
  format fix flagged in the `TextDisplay` loader (the header byte isn't
  currently accounted for in the glyph offset) — it will ship alongside a
  font-maker tool.
- A packaged, themed DearPyGui build so the app stops looking like "raw
  dearpygui with default widgets".
- 65C02 opcode support.

**Open issues in GitHub milestone "v0.3 Release - Development Tools":**

- [#5](https://github.com/ricky-groenewald/py6502/issues/5) — Add 65c02 opcode support
- [#19](https://github.com/ricky-groenewald/py6502/issues/19) — Complete assembler solution
- [#21](https://github.com/ricky-groenewald/py6502/issues/21) — Customize and package dearpygui/imgui
- [#24](https://github.com/ricky-groenewald/py6502/issues/24) — Enable saving of code snippets
- [#26](https://github.com/ricky-groenewald/py6502/issues/26) — Character Map / Sprite Editors

---

## Beyond v0.3

Not scheduled, but on the "would love to" list and worth recording so later
design decisions don't accidentally close the door on them:

- Additional 6502 machines: Commodore 64, BBC Micro, Atari 2600, Ben Eater
  breadboard computer. The IaC config format is explicitly designed so these
  arrive as new YAML presets + new Cython components, not as new `System`
  subclasses.
- A rewind system layered on the v0.2 save states
  ([#75](https://github.com/ricky-groenewald/py6502/issues/75)), built on
  the fact that every `Component` already owns all its mutable state.
- A headless mode for batch-running assembly programs (useful for CI,
  teaching, and test authoring).
- A web build via Pyodide or a native WASM recompile of the Cython core.

None of these are promises. They are here so that when a v0.1 or v0.2 design
decision threatens to make one of them impossible, that threat is visible.

---

## Git workflow

Releases cut from `main`, day-to-day work lands on `dev`.

- **Every feature** goes onto a feature branch and reaches `dev` via a pull
  request. Even though there is only one human contributor right now, the
  PR gate exists as a forcing function for code review and as the natural
  place to run CI and the sim-perf review agent.
- **Versioned releases** (v0.1, v0.2, v0.3, …) ship by PRing `dev` into
  `main` and tagging the merge commit. `main` is therefore always "a real
  release is here", never "whatever was last pushed".
- **Hotfixes** to a shipped release branch off `main`, land via PR back into
  `main`, and are then merged down into `dev`.

Force pushes to `main` and `dev` are off-limits. Force pushes to feature
branches are fine until they are reviewed; after review, prefer fixup
commits + a clean rebase at merge time over force-pushing a re-authored
history.

---

## Keeping this file and GitHub in sync

GitHub milestones and issues are the source of truth. This file is a
human-readable snapshot plus the *why*. The `/roadmap` skill (see
`.claude/skills/roadmap/`) uses the `gh` CLI to reconcile the two in either
direction: pulling the current issue list into this document, or opening
stubs on GitHub for any scope mentioned here that doesn't yet have an
issue.

Whenever scope changes — something drops, something moves between
milestones, a non-goal becomes a goal — update **both** the GitHub milestone
and the relevant section above in the same PR.
