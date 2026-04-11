"""
CYTHON SYSTEM ORCHESTRATION CLASS DECLARATIONS

Simulator definitions and functions for a complete system orchestrator
"""
from py6502.sim.cpu.mos6502 cimport MOS6502, Registers
from py6502.sim.bus.buscontroller cimport BusController
from py6502.sim.bus.memory cimport Memory
from py6502.sim.system.config import SystemConfig

cdef class System:
    cdef MOS6502 _cpu
    cdef unsigned long _cpu_hz
    cdef BusController _bus
    cpdef void run_cycles(self, unsigned long cpu_cycles)
    cpdef void run_for_microseconds(self, unsigned long microseconds)
    cpdef void reset(self)
    cpdef void load_binary(self, str dest_memory, list data, int start_addres)
    cpdef Registers get_registers(self)
