from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension("py6502sim.component", ["src/py6502sim/component.pyx"]),
    Extension("py6502sim.memory", ["src/py6502sim/memory.pyx"]),
    Extension("py6502sim.controller", ["src/py6502sim/controller.pyx"]),
    Extension("py6502sim.processor", ["src/py6502sim/processor.pyx"]),
]

setup(
    ext_modules=cythonize(extensions),
)
