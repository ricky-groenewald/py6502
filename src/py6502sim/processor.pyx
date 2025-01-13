"""
CYTHON MOS6502 PROCESSOR CLASS IMPLEMENTATIONS

Simulator definitions and functions for the main 6502 micro processor
"""
from libc.stdlib cimport malloc, free
from libc.string cimport memset
from cython cimport boundscheck, wraparound, compiled
from .component cimport Component

# Compile-Time Definitions
DEF CARRY_FLAG = 0b00000001
DEF ZERO_FLAG = 0b00000010
DEF IRQ_FLAG = 0b00000100
DEF DECIMAL_FLAG = 0b00001000
DEF BRK_FLAG = 0b00010000
DEF OVERFLOW_FLAG = 0b01000000
DEF NEGATIVE_FLAG = 0b10000000

class InvalidOPCode(Exception):
    """
    Exception raised for invalid OPCODEs
    """

cdef class MOS6502:
    """
    Class definition for the main MOS 6502 processor

    Based on the 1976 revision of the MCS6502 processor
    """
    
    def __init__(self, Component memory_bus) -> None:
        # Initialize internal and external variables
        self._memory_bus = memory_bus
        self._cycle_number = 0x00
        self._current_op_code = 0x00
        self._current_data = 0x00
        self._current_address = 0x00FF # Default address at reset
        self._write_buffer = 0x00
        self._write_buffer_flag = False
        self._interrupt_flag = 0 # 0 = None, 1 = IRQ, 2 = NMI, 3 = RESET

        # Initialize registers
        self._registers.ACC = 0x00
        self._registers.X = 0x00
        self._registers.Y = 0x00
        self._registers.PC = 0x0000
        self._registers.S = 0x00
        self._registers.P = 0b00110100
        # Status Register (P) reference:
            # Bit 0 - Carry (C)
            # Bit 1 - Zero (Z)
            # Bit 2 - IRQ Disable (I)
            # Bit 3 - Decimal Mode (D)
            # Bit 4 - BRK Command (B)
            # Bit 5 - UNUSED
            # Bit 6 - Overflow (V)
            # Bit 7 - Negative (N)

        # Initialize instruction functions
        memset(&self._instructions[0][0], 0, sizeof(instruction_func) * 256 * 2)
        self._current_instruction = NULL
        self._next_instruction = NULL

        # Define OPCODE instruction functions

    cdef void clock(self):
        if self._current_instruction is not NULL:
            self._current_instruction(self)
        elif self._interrupt_flag:
            self.handle_interrupt()
        else:
            self.load_op_code()

    cdef void load_op_code(self) except *:
        self._current_op_code = self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = self._instructions[self._current_op_code][0]
        self._next_instruction = self._instructions[self._current_op_code][1]

        if self._current_instruction is NULL:
            raise InvalidOPCode(f'Invalid OPCODE: 0x{self._current_op_code:02X}')

        self._registers.PC += 1
        self._cycle_number = 1

    cdef void send_reset(self):
        print(f'Sending reset to the processor')

    cdef void send_irq(self):
        print(f'Sending IRQ to the processor')

    cdef void send_nmi(self):
        print(f'Sending NMI to the processor')

    cpdef Registers get_registers(self):
        return self._registers



    cpdef unsigned char get_current_op_code(self):
        return self._current_op_code

    cpdef unsigned char get_current_data(self):
        return self._current_data

    cpdef unsigned short get_current_address(self):
        return self._current_address

    cpdef void set_registers(self, Registers registers):
        self._registers = registers

    cpdef void set_current_op_code(self, unsigned char op_code):
        self._current_op_code = op_code

    cpdef void set_current_data(self, unsigned char data):
        self._current_data = data

    cpdef void set_current_address(self, unsigned short address):
        self._current_address = address
