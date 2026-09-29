"""
Hot-path guard: no Python code may run inside a sim call.

The frontend makes one coarse call per frame, and everything under it
must stay in compiled Cython (performance rule 1 in
``src/py6502/sim/CLAUDE.md``). A ``sys.setprofile`` hook sees every
Python function call (``call``) and every builtin called from Python
code (``c_call``). Compiled Cython code fires neither, so a clean run
records nothing, and any name recorded is Python code that leaked into
the loop.

What this does not catch: C-API work done inside compiled code, such as
a dict lookup, an attribute read on a Python object, or a call through
an untyped reference. None of those run Python code, so the profiler
cannot see them. They cost time instead, which is what the throughput
numbers in ``docs/PERFORMANCE.md`` are for.
"""
import sys
from importlib import resources

from py6502.sim.system import CpuSpec, MemoryRegion, System, SystemConfig


APPLE1_PRESET = resources.files("py6502.sim.assets").joinpath("presets/apple1.yaml")

# Wozmon keeps the typed line at $0200 and the parsed examine address
# in XAML/XAMH. Apple I keys arrive with bit 7 set.
WOZMON_IN = 0x0200
WOZMON_XAML = 0x24
WOZMON_XAMH = 0x25


def _python_calls(fn, *args) -> list[str]:
    """
    Run ``fn(*args)`` under a profile hook and return the qualified name
    of every Python function or builtin it called. The hook's own
    removal (``sys.setprofile``) is the one call left out.
    """
    calls: list[str] = []

    def hook(frame, event, arg):
        if event == "call":
            calls.append(frame.f_code.co_qualname)
        elif event == "c_call" and arg is not sys.setprofile:
            calls.append(getattr(arg, "__qualname__", repr(arg)))

    previous = sys.getprofile()
    sys.setprofile(hook)
    try:
        fn(*args)
    finally:
        sys.setprofile(previous)
    return calls


def _leaked(calls: list[str]) -> str:
    """Failure message: each leaked name once, in the order it first ran."""
    return "Python ran inside the sim call: " + ", ".join(dict.fromkeys(calls))


def test_guard_sees_python_calls() -> None:
    """
    Control: the hook must report a plain Python call. If a Python or
    Cython upgrade ever changes what the profiler reports, this fails
    instead of the guards below passing without checking anything.
    """
    def python_helper() -> int:
        return 1

    assert _python_calls(python_helper) == [python_helper.__qualname__]


def test_run_cycles_on_bare_ram_makes_no_python_calls() -> None:
    """
    The CPU and bus alone. Zeroed RAM makes the CPU loop on BRK through
    a $0000 vector, which exercises fetch, stack writes and vector reads.
    """
    config = SystemConfig(
        version=1, id="guard", name="Guard", description="",
        cpu=CpuSpec(type="MOS6502", hz=1_000_000),
        memory=(MemoryRegion(name="RAM", start=0x0000, size=0x10000),),
    )
    system = System(config)

    calls = _python_calls(system.run_cycles, 2_000_000)
    assert calls == [], _leaked(calls)


def test_apple1_frames_make_no_python_calls() -> None:
    """
    The whole frame path: keyboard reads, display writes, the DSP busy
    timer in the tick hook, and ``sync_display``. Types ``FF00`` and
    Return into wozmon, then runs one second of 60 Hz frames, each call
    under the hook, the way the frontend drives the sim.
    """
    system = System.from_yaml_file(APPLE1_PRESET)
    for _ in range(10):
        system.run_for_microseconds(16667)  # boot into wozmon's input loop
    for key in b"FF00\r":
        assert system.send_key(key)

    calls: list[str] = []
    for _ in range(60):
        calls += _python_calls(system.run_for_microseconds, 16667)
    assert calls == [], _leaked(calls)

    # Prove the typed path ran inside the guarded calls. The framebuffer
    # can't show it: the blinking cursor changes it on its own. Wozmon
    # stores a key, then echoes it before reading the next one, and every
    # echo after the first waits for the DSP busy timer that only the
    # tick hook clears.
    typed = [system.peek(WOZMON_IN + i) for i in range(5)]
    assert typed == [0xC6, 0xC6, 0xB0, 0xB0, 0x8D]  # "FF00" + Return
    assert (system.peek(WOZMON_XAMH), system.peek(WOZMON_XAML)) == (0xFF, 0x00)
