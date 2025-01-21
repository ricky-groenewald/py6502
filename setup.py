from setuptools import setup, Extension
from Cython.Build import cythonize

include_dirs = [
    "src/py6502sim",
    # "src/py6502sim/audio",
    "src/py6502sim/bus",
    "src/py6502sim/cpu",
    # "src/py6502sim/peripheral",
    # "src/py6502sim/ppu",
]

extensions = [
    Extension("py6502sim.bus.component", ["src/py6502sim/bus/component.pyx"], include_dirs=include_dirs),
    Extension("py6502sim.bus.memory", ["src/py6502sim/bus/memory.pyx"], include_dirs=include_dirs),
    Extension("py6502sim.bus.buscontroller", ["src/py6502sim/bus/buscontroller.pyx"], include_dirs=include_dirs),
    Extension("py6502sim.cpu.mos6502", ["src/py6502sim/cpu/mos6502.pyx"], include_dirs=include_dirs),
]

setup(
    ext_modules=cythonize(extensions),
)
