# py6502

> **Emulator of everything 6502.** A cycle-accurate 6502 simulator and a
> DearPyGui frontend, aimed at hobbyists, educators, and retro-computing
> enthusiasts.

`py6502` is a single Python package split into two halves:

- **`py6502.sim`** — a Cython simulator. Cycle-accurate 6502 core, flat 64K
  memory bus, pluggable components (RAM, ROM, displays, peripherals), and a
  `System` facade that builds a whole machine from an IaC config file.
  Designed so the steady-state hot path never drops back into Python.
- **`py6502.ui`** — a DearPyGui frontend. Spins up a window, loads a system
  from a preset or a user YAML file, and drives it with a single coarse
  call per UI frame.

The roadmap is Apple I first, NES next, then a development-tools release
with an integrated assembler, snippet editor, and sprite tools. See
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## Status

v0.1 is in active development. It ships a cycle-accurate 6502, the Apple I
preset, a debug panel with step-level debugging, a system selector, a
binary loader, and configurable settings.

## Prerequisites

- **Python 3.12+**
- A C toolchain capable of building Cython extensions
- **Custom DearPyGui build** — py6502 uses a patched DearPyGui with
  `GL_LINEAR` replaced by `GL_NEAREST` to disable texture filtering for
  pixel-accurate rendering. Without this patch, the 256x240 framebuffer
  appears blurry when scaled. See
  [DearPyGui#773](https://github.com/hoffstadt/DearPyGui/issues/773) for
  context and the workaround details (search for the `GL_NEAREST` fix in
  the issue discussion).

## Install and run

```bash
# From a clone of the repo:
pip install -e .

# Run the UI
python -m py6502
```

The build uses `-O3 -march=native -flto` — extensions are tuned to the host
CPU and may need a rebuild when moving between machines.

## Usage

### System selector

On launch, py6502 shows the system selector dialog. Bundled presets
(currently Apple I) appear automatically. You can also load custom system
configurations from YAML files — previously loaded user configs are
remembered across sessions.

A "Start with last used system" setting skips the selector on startup.

### Debug panel

The debug panel shows CPU registers (PC, A, X, Y, S), status flags
(N, V, B, D, I, Z, C), the current opcode with its decoded mnemonic, and
a hex + ASCII memory monitor with page navigation.

Controls:
- **Play / Pause** — start or stop continuous execution
- **Step** — advance one full 6502 instruction (only when paused)
- **Cycle** — advance one CPU clock cycle (only when paused)
- **Reset** — reset the CPU and all peripherals

### Loading binaries

**File > Load Binary** opens a dialog where you select a `.bin` or `.rom`
file, choose a target memory region from the system config, and specify a
hex offset within that region.

### Settings

**File > Settings** opens the settings window:
- **Start with last used system** — skip the system selector on startup
- **Halt on invalid opcode** — raise an error on undefined opcodes
- **Halt on unmapped memory** — raise an error on access to unmapped
  addresses

Settings are saved to `py6502_settings.json` and persist across sessions.

## Repository layout

```
src/py6502/            single top-level package
├── sim/               Cython simulator
│   ├── bus/           Component, BusController, Memory
│   ├── cpu/           MOS6502 (cycle-accurate, precomputed dispatch)
│   ├── graphics/      TextDisplay, Font
│   ├── peripherals/   Apple1Display, Apple1Keyboard
│   ├── system/        System facade, YAML loader, component registry
│   └── assets/        Bundled ROMs, fonts, preset configs
└── ui/                DearPyGui frontend
    ├── app.py         Py6502App — viewport, menu bar, frame loop
    ├── themes.py      ThemeManager
    ├── windows/       Video, debug, system selector, binary loader, etc.
    └── utils/         Key handler, settings, preset discovery
docs/                  ARCHITECTURE, SYSTEM_CONFIG, ROADMAP
play/                  Hand-written 6502 asm + scratch experiments
```

## Documentation

The canonical docs are under [`docs/`](docs/):

- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md) — runtime model (System, bus,
  CPU, peripherals, frontend loop).
- [`SYSTEM_CONFIG.md`](docs/SYSTEM_CONFIG.md) — the IaC config format used
  to describe machines and the component registry.
- [`ROADMAP.md`](docs/ROADMAP.md) — milestones, scope, non-goals, git
  workflow.

## Contributing

The project currently has one human contributor, but reviews and CI gates
are set up as if it had many — it's good hygiene and it keeps the door
open. Every feature goes through a feature branch and a PR into `dev`;
versioned releases ship by PRing `dev` into `main`.

Before opening a PR:

1. Read the relevant `CLAUDE.md` (root + per-package).
2. If your change touches a hot path in `py6502.sim`, re-read the
   performance rules in `src/py6502/sim/CLAUDE.md`. "No Python loops in
   steady state" is non-negotiable.
3. Run the tests (once the v0.1 harness lands).

## License

Copyright retained by Ricky Groenewald. `py6502` is free to use and
redistribute for personal, educational, and hobbyist purposes; commercial
use is not permitted. See [`LICENSE`](LICENSE) for the full terms.
