from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension("py6502sim.component", ["src/py6502sim/component.pyx"]),
    Extension("py6502sim.memory", ["src/py6502sim/memory.pyx"]),
]

setup(
    ext_modules=cythonize(extensions),
)
