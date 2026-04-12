# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this project is

`py6502` is "Emulator of everything 6502" — a cycle-accurate 6502 simulator
(Cython) plus a DearPyGui frontend, aimed at hobbyists, educators, and
retro-computing enthusiasts. The plan is Apple I first (v0.1), NES next
(v0.2), then a full development-tools release (v0.3). Read
[`docs/ROADMAP.md`](docs/ROADMAP.md) for the narrative and GitHub milestones
for the authoritative schedule.

## Canonical docs (read these before large changes)

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — runtime model: how
  `System` / `BusController` / `MOS6502` / peripherals fit together, the
  clocking model, and the frontend loop.
- [`docs/SYSTEM_CONFIG.md`](docs/SYSTEM_CONFIG.md) — the IaC config format
  used to describe machines, the component registry, and the
  `SystemConfig` / `BusSpec` / `MemoryRegion` / `ComponentSpec` dataclasses.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — milestones, scope, non-goals, and
  git workflow.

## Repository layout

```
src/py6502/            single top-level package
├── sim/               Cython simulator (the hot path)
│   ├── bus/           Component, BusController, Memory, EmptyAddress
│   ├── cpu/           MOS6502 (cycle-accurate, precomputed dispatch)
│   ├── graphics/      TextDisplay + Font
│   ├── peripherals/   Apple1Display, Apple1Keyboard, future devices
│   ├── system/        System façade + YAML loader + component registry
│   └── assets/        Bundled BIOS ROMs, fonts, preset configs
└── ui/                DearPyGui frontend (Py6502App + windows/systems/utils)
docs/                  ARCHITECTURE, SYSTEM_CONFIG, ROADMAP
play/                  Scratch 6502 asm + binaries; not part of the package
```

## Commands

- **Build / install** (rebuilds Cython extensions):
  `pip install -e .` — needed after any change to a `.pyx` or `.pxd`.
- **Run the UI**: `python -m py6502` → `src/py6502/__main__.py` (which
  just calls `Py6502App().run()`).
- **Tests**: `pytest`. Fixtures + CI land with v0.1. Klaus Dormann /
  Bruce Clark suites run under `@pytest.mark.slow`.
- **Python**: `>=3.12`. Compile flags in `setup.py`: `-O3 -march=native -flto`
  (tuned for the host CPU — expect rebuilds when moving machines).

## Workflow and expectations

- **Git**: every feature lands via a PR from a feature branch into `dev`.
  Versioned releases PR `dev` → `main`. Never force-push `main` or `dev`.
  See `docs/ROADMAP.md` §Git workflow. **Every commit and PR goes
  through the `/commit` skill** — it enforces the protected-branch
  gate, feature-branch naming, and commit-message shape. Never run
  `git commit` or `gh pr create` out-of-band.
- **Commit messages**: keep them as concise as the change allows — a
  single imperative headline is ideal; a short body is fine when the
  change spans multiple concerns and the *why* isn't obvious from the
  diff. Do **not** add a `Co-Authored-By: Claude …` trailer or any
  variation of it. Human authorship is the default.
- **Scope discipline**: don't add error handling, abstractions, or
  backwards-compat shims beyond what the task requires. Don't design for
  hypothetical future requirements — when a future requirement actually
  arrives, refactor then.
- **No drive-by refactors**: if you spot something unrelated that looks
  wrong, leave a GitHub issue, don't fix it in the same PR.
- **Documentation**: the three docs above are the contract. If a change
  invalidates anything in them, update the doc in the same PR as the code.
- **Performance**: the simulator's hot-path rules live in
  `src/py6502/sim/CLAUDE.md` and are load-bearing. When in doubt, "no Python
  loops in steady state" is the one rule that outranks everything.

## What not to touch

- `play/` — Ricky's scratchpad. Don't normalise or refactor anything under
  it; treat it as read-only input data.
- `src/py6502/ui/py6502ui.py` — the legacy monolithic UI. It stays as a
  feature-parity reference until the new `Py6502App` shell replaces it in
  v0.1. Don't port new features into it.
