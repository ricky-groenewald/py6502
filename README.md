# py6502

> **Emulator of everything 6502.** A cycle-accurate 6502 simulator and a
> DearPyGui frontend, aimed at hobbyists, educators, and retro-computing
> enthusiasts.

`py6502` is a single Python package split into two halves:

- **`py6502.sim`** — a Cython simulator. Cycle-accurate 6502 core, flat 64K
  memory bus, pluggable components (RAM, ROM, displays, peripherals), and a
  `System` façade that builds a whole machine from an IaC config file.
  Designed so the steady-state hot path never drops back into Python.
- **`py6502.ui`** — a DearPyGui frontend. Spins up a window, loads a system
  from a preset or a user YAML file, and drives it with a single coarse
  call per UI frame.

The roadmap is Apple I first, NES next, then a development-tools release
with an integrated assembler, snippet editor, and sprite tools. See
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## Status

Pre-alpha. v0.1 is in active development — it will ship a cycle-accurate
6502, the Apple I preset, the new UI shell, a pytest harness wired up to
the Klaus Dormann / Bruce Clark functional test suites, and CI.

The codebase is being prepared for first-class LLM-assisted development; the
top-level `CLAUDE.md` and the docs under `docs/` are part of that prep.

## Install and run

```bash
# From a clone of the repo:
pip install -e .

# Run the UI
python -m py6502
```

Requirements: Python 3.12+, a C toolchain that can build the Cython
extensions, and whatever your platform needs for DearPyGui. The build uses
`-O3 -march=native -flto` — extensions are tuned to the host CPU and may
need a rebuild when moving between machines.

## Repository layout

```
src/py6502/            single top-level package
├── sim/               Cython simulator
└── ui/                DearPyGui frontend
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
