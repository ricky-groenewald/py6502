from setuptools import setup, Extension
from Cython.Build import cythonize

include_dirs = [
    "src/py6502/sim",
    "src/py6502/sim/bus",
    "src/py6502/sim/cpu",
    "src/py6502/sim/graphics",
    "src/py6502/sim/peripherals",
    "src/py6502/sim/system",
]

common_cflags = ['-O3', '-march=native', '-flto']
common_ldflags = ['-flto']

def ext(module, source):
    return Extension(
        module,
        [source],
        include_dirs=include_dirs,
        extra_compile_args=common_cflags,
        extra_link_args=common_ldflags,
    )

extensions = [
    ext("py6502.sim.bus.component",                "src/py6502/sim/bus/component.pyx"),
    ext("py6502.sim.bus.memory",                   "src/py6502/sim/bus/memory.pyx"),
    ext("py6502.sim.bus.buscontroller",            "src/py6502/sim/bus/buscontroller.pyx"),
    ext("py6502.sim.bus.emptyaddress",             "src/py6502/sim/bus/emptyaddress.pyx"),
    ext("py6502.sim.cpu.mos6502",                  "src/py6502/sim/cpu/mos6502.pyx"),
    ext("py6502.sim.graphics.textdisplay",         "src/py6502/sim/graphics/textdisplay.pyx"),
    ext("py6502.sim.peripherals.apple1_display",   "src/py6502/sim/peripherals/apple1_display.pyx"),
    ext("py6502.sim.peripherals.apple1_keyboard",  "src/py6502/sim/peripherals/apple1_keyboard.pyx"),
    ext("py6502.sim.system.system",                "src/py6502/sim/system/system.pyx"),
]

setup(
    ext_modules=cythonize(extensions),
)
