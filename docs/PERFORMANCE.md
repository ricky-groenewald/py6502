# Performance

Throughput records for the simulator, and the method used to take them.
The hot-path rules live in
[`src/py6502/sim/CLAUDE.md`](../src/py6502/sim/CLAUDE.md); this file
holds the numbers that show whether a change kept to them.

Each release adds its own baseline section at the end. Earlier sections
stay as they are, so the file doubles as the history.

## Reading the numbers

- **Numbers are per machine.** Compare before and after on the same
  machine, same build setup, same sitting. Never compare numbers taken
  on two different machines.
- **Measure before and after back to back.** The baselines below are
  reference points, not the "before" for your PR. Measure the base
  branch and your branch one after the other:

  ```bash
  git switch dev && pip install -e . && python bench.py <klaus.bin>
  git switch <your-branch> && pip install -e . && python bench.py <klaus.bin>
  ```

- **Expect noise.** On the dev machine, repeated runs on one evening put
  the best Klaus result anywhere between 213 and 227 Mcycles/s. Treat a
  difference smaller than about 7% as noise. If it matters, rerun both
  sides.
- **No thresholds in pytest.** Timing depends on the machine and its
  load, so it lives here. The test suite checks structure instead (see
  below).

## Hot-path guard

`tests/test_hot_path.py` runs sim calls under a `sys.setprofile` hook
and fails if any Python function runs inside them. The failure names
each function. It covers `run_cycles` on bare RAM and Apple I frames
with keys typed, plus a control that proves the hook still sees Python
calls.

It cannot see C-API work inside compiled code, such as a dict lookup or
a call through an untyped reference, because no Python code runs.
Those costs show up here instead, as lower throughput.

## How to measure

1. **Rebuild:** `pip install -e .`. The build runs in an isolated
   environment with the latest Cython from PyPI, not the Cython in your
   venv. The first line of any generated `.c` file (for example
   `src/py6502/sim/cpu/mos6502.c`) names the version that was used.
2. **Get the Klaus Dormann functional test binary** from
   [amb5l/6502_65C02_functional_tests](https://github.com/amb5l/6502_65C02_functional_tests).
   It is GPL-3.0, so it stays out of this repository. The script runs it
   for 96,247,419 cycles and checks for the pass marker `$F0` at
   `$0200`. A different build of the binary can need a different cycle
   count.
   [#50](https://github.com/ricky-groenewald/py6502/issues/50) replaces
   this step with runners under `scripts/` that pin the upstream commit.
3. **Run the script below** as
   `python bench.py path/to/6502_functional_test.bin`. It runs four
   workloads in rotation for five rounds and keeps the best time of
   each. Rotating stops one workload from always running first.

```python
import sys
from importlib import resources
from pathlib import Path
from time import perf_counter

from py6502.sim.system import CpuSpec, MemoryRegion, System, SystemConfig

APPLE1 = resources.files("py6502.sim.assets").joinpath("presets/apple1.yaml")
KLAUS_CYCLES = 96_247_419


def klaus(binary, mode=None):
    """Bare 64K RAM, test binary at $0000, start at $0400."""
    system = System(SystemConfig(
        version=1, id="klaus", name="Klaus", description="",
        cpu=CpuSpec(type="MOS6502", hz=1_000_000),
        memory=(MemoryRegion(name="RAM", start=0x0000, size=0x10000),),
    ))
    system.load_binary_at(0x0000, binary)
    regs = system.get_registers()
    regs["INTERRUPT_TYPE"] = 0
    regs["PC"] = 0x0400
    system.set_registers(regs)
    if mode is not None:
        system.set_invalid_opcode_mode(mode)
    start = perf_counter()
    system.run_cycles(KLAUS_CYCLES)
    elapsed = perf_counter() - start
    assert system.peek(0x0200) == 0xF0, "Klaus did not pass"
    return elapsed


def apple1_cycles():
    """Wozmon idling in its keyboard-poll loop."""
    system = System.from_yaml_file(APPLE1)
    start = perf_counter()
    system.run_cycles(50_000_000)
    return perf_counter() - start


def apple1_frames():
    """600 frontend-shaped calls: 10 s of 60 Hz frames, render included."""
    system = System.from_yaml_file(APPLE1)
    start = perf_counter()
    for _ in range(600):
        system.run_for_microseconds(16667)
    return perf_counter() - start


binary = Path(sys.argv[1]).read_bytes()
workloads = {
    "Klaus, legal opcodes": lambda: klaus(binary),
    "Klaus, mode 2": lambda: klaus(binary, mode=2),
    "Apple I, run_cycles": apple1_cycles,
    "Apple I, frames": apple1_frames,
}
best = dict.fromkeys(workloads, float("inf"))
for _ in range(5):  # rotate, so no workload always runs first
    for name, run in workloads.items():
        best[name] = min(best[name], run())

print(f"Klaus, legal opcodes  {KLAUS_CYCLES / best['Klaus, legal opcodes'] / 1e6:.0f} Mcycles/s")
print(f"Klaus, mode 2         {KLAUS_CYCLES / best['Klaus, mode 2'] / 1e6:.0f} Mcycles/s")
print(f"Apple I, run_cycles   {50_000_000 / best['Apple I, run_cycles'] / 1e6:.0f} Mcycles/s")
print(f"Apple I, one frame    {best['Apple I, frames'] / 600 * 1e6:.0f} µs")
```

## v0.1 baseline (2026-09-29)

| Setup    |                                                   |
|----------|---------------------------------------------------|
| Machine  | Apple M1 Pro, macOS 26.7                          |
| Python   | 3.14.6                                            |
| Cython   | 3.3.0                                             |
| Compiler | Apple clang 21.0.0, `-O3 -march=native -flto`     |
| Sim code | commit `0e4ecf8`                                  |

| Workload                                            | Result        |
|-----------------------------------------------------|---------------|
| Klaus functional test, legal opcodes                | 220 Mcycles/s |
| Klaus functional test, illegal-opcode mode 2        | 220 Mcycles/s |
| Apple I preset, `run_cycles`                        | 239 Mcycles/s |
| Apple I preset, one 60 Hz frame (16,667 cycles)     | 127 µs        |

- Mode 2 matches legal opcodes. Klaus never executes an illegal opcode,
  so the overlay adds no cost to the legal path.
- About 70 µs of the Apple I frame is the 16,667 CPU cycles. Most of the
  rest is the display render in `sync_display`.
- [#65](https://github.com/ricky-groenewald/py6502/issues/65) compares
  the v0.2 Apple I numbers against these rows.
