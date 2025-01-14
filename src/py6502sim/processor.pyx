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
        self._temp_data = 0x00
        self._temp_address = 0x0000
        self._interrupt_flag = 0 # 0 = None, 1 = IRQ, 2 = NMI, 3 = RESET

        # Initialize registers with RESET values
        self._registers.OPCODE = 0x00
        self._registers.ACC = 0x00
        self._registers.X = 0x00
        self._registers.Y = 0x00
        self._registers.PC = 0x00FF
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
        # TODO: Implement OPCODE instruction function map

    ###
    #   CONTROL FUNCTIONS
    ###
    cdef void clock(self):
        if self._current_instruction is not NULL:
            self._current_instruction(self)
        elif self._interrupt_flag:
            self.handle_interrupt()
        else:
            self.load_op_code()

    cdef void send_reset(self):
        # TODO: Implement reset logic
        print(f'Sending reset to the processor')

    cdef void send_irq(self):
        # TODO: Implement IRQ logic
        print(f'Sending IRQ to the processor')

    cdef void send_nmi(self):
        # TODO: Implement NMI logic
        print(f'Sending NMI to the processor')

    cdef void handle_interrupt(self):
        # TODO: Implement interrupt logic
        print(f'Handling interrupt')

    cdef void load_op_code(self) except *:
        self._registers.OPCODE = self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = self._instructions[self._registers.OPCODE][0]
        self._next_instruction = self._instructions[self._registers.OPCODE][1]

        if self._current_instruction is NULL:
            raise InvalidOPCode(f'Invalid OPCODE: 0x{self._registers.OPCODE:02X}')

        self._cycle_number = 0 # Reset cycle number (Read Addressing Mode notes)

    ###
    #   ADDRESSING MODES
    #
    #   Note: Cycle number expects to start and end at 0 for each addressing mode. The final
    #   cycle number only ends on a non-zero value if a page cross occured during certain addressing
    #   modes that involve the X or Y register.
    ###
    cdef void absolute(self):
        self._registers.PC += 1
        if not self._cycle_number:
            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        else:
            self._temp_address |= (self._memory_bus.execute(self._registers.PC, 0, 1) << 8)
            self._cycle_number = 0
            self._current_instruction, self._next_instruction = self._next_instruction, NULL

    cdef void absolute_x(self):
        self._registers.PC += 1
        if not self._cycle_number:
            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        else:
            self._temp_address |= (self._memory_bus.execute(self._registers.PC, 0, 1) << 8)
            self._current_instruction, self._next_instruction = self._next_instruction, NULL

            if (self._registers.X + self._temp_address) & 0xFF00 == self._temp_address & 0xFF00:
                self._cycle_number = 0 # No page cross, 1 otherwise

            self._temp_address += self._registers.X

    cdef void absolute_y(self):
        self._registers.PC += 1
        if not self._cycle_number:
            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        else:
            self._temp_address |= (self._memory_bus.execute(self._registers.PC, 0, 1) << 8)
            self._current_instruction, self._next_instruction = self._next_instruction, NULL

            if (self._registers.Y + self._temp_address) & 0xFF00 == self._temp_address & 0xFF00:
                self._cycle_number = 0 # No page cross, 1 otherwise

            self._temp_address += self._registers.Y

    cdef void immediate(self): # Also handles relative addressing
        self._registers.PC += 1
        self._temp_address = self._registers.PC
        self._current_instruction, self._next_instruction = self._next_instruction, NULL
        self._cycle_number = 0
        self._current_instruction(self)

    cdef void indirect_x(self):
        if not self._cycle_number:
            self._registers.PC += 1
            self._temp_data = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._memory_bus.execute(self._temp_data, 0, 1) # Discard data
            self._cycle_number += 1
        elif self._cycle_number == 2:
            self._temp_address = self._memory_bus.execute(
                (self._temp_data + self._registers.X) & 0xFF,
                0,
                1
            )
            self._cycle_number += 1
        else:
            self._temp_address |= (
                self._memory_bus.execute(
                    (self._temp_data + self._registers.X + 1) & 0xFF,
                    0,
                    1
                ) << 8
            )
            self._cycle_number = 0
            self._current_instruction, self._next_instruction = self._next_instruction, NULL

    cdef void indirect_y(self):
        if not self._cycle_number:
            self._registers.PC += 1
            self._temp_data = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._temp_address = self._memory_bus.execute(
                self._temp_data,
                0,
                1
            )
            self._cycle_number += 1
        else:
            self._temp_address |= (
                self._memory_bus.execute(
                    (self._temp_data + 1) & 0xFF,
                    0,
                    1
                ) << 8
            )

            if (self._registers.Y + self._temp_address) & 0xFF00 == self._temp_address & 0xFF00:
                self._cycle_number = 0 # No page cross, 2 otherwise

            self._temp_address += self._registers.Y
            self._current_instruction, self._next_instruction = self._next_instruction, NULL

    cdef void zero_page(self):
        self._registers.PC += 1
        self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction, self._next_instruction = self._next_instruction, NULL
        self._cycle_number = 0

    cdef void zero_page_x(self):
        if not self._cycle_number:
            self._registers.PC += 1
            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        else:
            self._memory_bus.execute(self._temp_address, 0, 1) # Discard data
            self._temp_address = (self._temp_address + self._registers.X) & 0xFF
            self._current_instruction, self._next_instruction = self._next_instruction, NULL
            self._cycle_number = 0

    cdef void zero_page_y(self):
        if not self._cycle_number:
            self._registers.PC += 1
            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        else:
            self._memory_bus.execute(self._temp_address, 0, 1) # Discard data
            self._temp_address = (self._temp_address + self._registers.Y) & 0xFF
            self._current_instruction, self._next_instruction = self._next_instruction, NULL
            self._cycle_number = 0

    ###
    #   OPCODE FUNCTIONS
    #
    #   Note: For expected cycle numbers, see Addressing Mode notes.
    ###
    cdef void ADC_SBC(self):
        self._temp_data = self._memory_bus.execute(self._temp_address, 0, 1)

        if (self._registers.OPCODE & 0x80): # SBC opcodes have bit 7 set
            self._temp_data ^= 0xff # Invert for subtraction

        cdef unsigned short result = (
            self._registers.ACC + self._temp_data + (1 if self._registers.P & CARRY_FLAG else 0)
        )

        # Set carry flag
        self._registers.P = (
            self._registers.P | CARRY_FLAG
            if result >> 8
            else self._registers.P & ~CARRY_FLAG
        )

        result &= 0xff

        # Set zero flag
        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if result
            else self._registers.P | ZERO_FLAG
        )

        # Set overflow flag
        self._registers.P = (
            self._registers.P | OVERFLOW_FLAG
            if ((self._registers.ACC ^ result) & (self._temp_data ^ result) & 0x80)
            else self._registers.P & ~OVERFLOW_FLAG
        )

        # Set negative flag
        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if result & 0x80
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._registers.ACC = result
        self._current_instruction = NULL
        self._registers.PC += 1

    # I hate BCD so much!
    cdef void ADC_SBC_BCD(self):
        pass

    ###
    #   GETTERS AND SETTERS
    ###
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
