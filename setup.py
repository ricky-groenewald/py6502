from setuptools import setup, Extension
from Cython.Build import cythonize

include_dirs = [
    "src/py6502sim",
    # "src/py6502sim/audio",
    "src/py6502sim/bus",
    "src/py6502sim/cpu",
    "src/py6502sim/graphics",
    "src/py6502sim/peripheral",
]

extensions = [
    Extension("py6502sim.bus.component", ["src/py6502sim/bus/component.pyx"], include_dirs=include_dirs, extra_compile_args=['-Ofast', '-march=native']),
    Extension("py6502sim.bus.memory", ["src/py6502sim/bus/memory.pyx"], include_dirs=include_dirs, extra_compile_args=['-Ofast', '-march=native']),
    Extension("py6502sim.bus.buscontroller", ["src/py6502sim/bus/buscontroller.pyx"], include_dirs=include_dirs, extra_compile_args=['-Ofast', '-march=native']),
    Extension("py6502sim.bus.emptyaddress", ["src/py6502sim/bus/emptyaddress.pyx"], include_dirs=include_dirs, extra_compile_args=['-Ofast', '-march=native']),
    Extension("py6502sim.cpu.mos6502", ["src/py6502sim/cpu/mos6502.pyx"], include_dirs=include_dirs, extra_compile_args=['-Ofast', '-march=native']),
    Extension("py6502sim.graphics.textdisplay", ["src/py6502sim/graphics/textdisplay.pyx"], include_dirs=include_dirs, extra_compile_args=['-Ofast', '-march=native']),
    Extension("py6502sim.peripheral.apple1", ["src/py6502sim/peripheral/apple1.pyx"], include_dirs=include_dirs, extra_compile_args=['-Ofast', '-march=native']),
]

setup(
    ext_modules=cythonize(extensions),
)
