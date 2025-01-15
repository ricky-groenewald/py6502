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
DEF IRQ_DISABLE_FLAG = 0b00000100
DEF DECIMAL_MODE_FLAG = 0b00001000
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
        self._incoming_interrupt_flag = 0 # 0 = None, 1 = IRQ, 2 = NMI, 3 = RESET
        self._page_cross_possible = False
        self._page_cross_occurred = False
        self._accumulator_addressing = False
        self._arithmetic_result = 0x0000
        self._branch_offset = 0x00

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
        self._current_instruction = &MOS6502.load_op_code
        self._next_instruction = NULL

        self._adc_sbc_opcodes[:] = [
                0x69, 0x6D, 0x65, 0x61, 0x71, 0x75, 0x7D, 0x79,
                0xE9, 0xED, 0xE5, 0xE1, 0xF1, 0xF5, 0xFD, 0xF9
            ]

        # Define OPCODE instruction functions
        # TODO: Implement OPCODE instruction function map

    ###
    #   CONTROL FUNCTIONS
    ###
    cdef void clock(self):
        if self._current_instruction is not NULL:
            self._current_instruction(self)
        elif self._incoming_interrupt_flag:
            self._registers.PC += 1
            self.handle_interrupt()
        else:
            self._registers.PC += 1
            self.load_op_code()

    # cdef void send_reset(self):
    #     print(f'Sending reset to the processor')

    # cdef void send_irq(self):
    #     print(f'Sending IRQ to the processor')

    # cdef void send_nmi(self):
    #     print(f'Sending NMI to the processor')

    # cdef void handle_interrupt(self):
    #     print(f'Handling interrupt')

    cdef void load_op_code(self) except *:
        self._registers.OPCODE = self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = self._instructions[self._registers.OPCODE][0]
        self._next_instruction = self._instructions[self._registers.OPCODE][1]

        if self._current_instruction is NULL:
            raise InvalidOPCode(f'Invalid OPCODE: 0x{self._registers.OPCODE:02X}')

        self._cycle_number = 0
        # We don't update the PC here, as we need to keep the registers consistent
        # with its value during the entire cycle

    # cdef void clear_decimal_mode(self):
    #     self._registers.P &= ~DECIMAL_MODE_FLAG

    #     # Change all ADC and SBC opcodes back to normal
    #     # For NES implementations, remove this FOR loop, but keep the flag update above
    #     for opcode in self._adc_sbc_opcodes:
    #         self._instructions[opcode][1] = &self.ADC_SBC

    # cdef void set_decimal_mode(self):
    #     self._registers.P |= DECIMAL_MODE_FLAG

    #     # Change all ADC and SBC opcodes to use BCD version
    #     # For NES implementations, remove this FOR loop, but keep the flag update above
    #     for opcode in self._adc_sbc_opcodes:
    #         self._instructions[opcode][1] = &self.ADC_SBC_BCD

    ###
    #   ADDRESSING MODES
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
            self._page_cross_possible = True

            if (self._registers.X + self._temp_address) & 0xFF00 != self._temp_address & 0xFF00:
                self._page_cross_occurred = True

            self._cycle_number = 0
            self._temp_address += self._registers.X

    cdef void absolute_y(self):
        self._registers.PC += 1
        if not self._cycle_number:
            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        else:
            self._temp_address |= (self._memory_bus.execute(self._registers.PC, 0, 1) << 8)
            self._current_instruction, self._next_instruction = self._next_instruction, NULL
            self._page_cross_possible = True

            if (self._registers.Y + self._temp_address) & 0xFF00 != self._temp_address & 0xFF00:
                self._page_cross_occurred = True

            self._cycle_number = 0
            self._temp_address += self._registers.Y

    cdef void accumulator(self):
        self._registers.PC += 1
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._accumulator_addressing = True
        self._current_instruction, self._next_instruction = self._next_instruction, NULL
        self._current_instruction(self)

    cdef void immediate(self): # Also handles relative addressing
        self._registers.PC += 1
        self._temp_address = self._registers.PC
        self._current_instruction, self._next_instruction = self._next_instruction, NULL
        self._current_instruction(self)

    cdef void implied(self):
        self._registers.PC += 1
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction, self._next_instruction = self._next_instruction, NULL
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
            self._page_cross_possible = True

            if (self._registers.Y + self._temp_address) & 0xFF00 != self._temp_address & 0xFF00:
                self._page_cross_occurred = True

            self._cycle_number = 0
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
    ###
    cdef void ADC_SBC(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
            self._page_cross_possible = False
            return

        self._temp_data = self._memory_bus.execute(self._temp_address, 0, 1)

        if (self._registers.OPCODE & 0x80): # SBC opcodes have bit 7 set
            self._temp_data ^= 0xff # Invert for subtraction

        self._arithmetic_result = (
            self._registers.ACC + self._temp_data + (1 if self._registers.P & CARRY_FLAG else 0)
        )

        # Set carry flag
        self._registers.P = (
            self._registers.P | CARRY_FLAG
            if self._arithmetic_result >> 8
            else self._registers.P & ~CARRY_FLAG
        )

        self._arithmetic_result &= 0xff

        # Set zero flag
        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if (self._arithmetic_result & 0xFF)
            else self._registers.P | ZERO_FLAG
        )

        # Set overflow flag
        self._registers.P = (
            self._registers.P | OVERFLOW_FLAG
            if ((self._registers.ACC ^ self._arithmetic_result) & (self._temp_data ^ self._arithmetic_result) & 0x80)
            else self._registers.P & ~OVERFLOW_FLAG
        )

        # Set negative flag
        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._arithmetic_result & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._registers.ACC = self._arithmetic_result
        self._current_instruction = NULL

    # I hate BCD so much!
    # cdef void ADC_SBC_BCD(self):
        # if self._page_cross_possible:
        #     # Run a discarding cycle if a page cross occured
        #     if self._page_cross_occurred:
        #         self._memory_bus.execute(self._temp_address, 0, 1)
        #         self._page_cross_occurred = False
        #     self._page_cross_possible = False
        #     return

    cdef void AND(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
            self._page_cross_possible = False
            return

        self._registers.ACC &= self._memory_bus.execute(self._temp_address, 0, 1)
        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.ACC
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.ACC & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )
        self._current_instruction = NULL

    cdef void ASL(self):
        if self._accumulator_addressing:
            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if self._registers.ACC & 0x80
                else self._registers.P & ~CARRY_FLAG
            )

            self._registers.ACC <<= 1

            self._registers.P = (
                self._registers.P & ~ZERO_FLAG
                if self._registers.ACC
                else self._registers.P | ZERO_FLAG
            )
            self._registers.P = (
                self._registers.P | NEGATIVE_FLAG
                if self._registers.ACC & 0x80
                else self._registers.P & ~NEGATIVE_FLAG
            )

            self._accumulator_addressing = False
            self._current_instruction = NULL
            return

        if self._page_cross_possible:
            # Run a discarding cycle after any addressing mode where page cross was possible
            self._memory_bus.execute(self._temp_address, 0, 1)
            self._page_cross_occurred = False
            self._page_cross_possible = False
            return

        if not self._cycle_number:
            self._temp_data = self._memory_bus.execute(self._temp_address, 0, 1)
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._memory_bus.execute(self._temp_address, self._temp_data, 0)
            self._cycle_number = 2
        else:
            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if self._temp_data & 0x80
                else self._registers.P & ~CARRY_FLAG
            )

            self._temp_data <<= 1
            self._memory_bus.execute(self._temp_address, self._temp_data, 0)

            self._registers.P = (
                self._registers.P & ~ZERO_FLAG
                if self._temp_data
                else self._registers.P | ZERO_FLAG
            )
            self._registers.P = (
                self._registers.P | NEGATIVE_FLAG
                if self._temp_data & NEGATIVE_FLAG
                else self._registers.P & ~NEGATIVE_FLAG
            )

            self._current_instruction = NULL

    cdef void BCC(self):
        if not self._cycle_number:
            self._branch_offset = self._memory_bus.execute(self._temp_address, 0, 1)
            if (self._registers.P & CARRY_FLAG):
                # Branch not taken
                self._current_instruction = NULL
            else:
                self._temp_address += self._branch_offset + 1
                self._cycle_number = 1
            return

        if self._cycle_number == 1:
            self._registers.PC = (self._registers.PC & 0xFF00) | (self._temp_address & 0xFF)
            self._memory_bus.execute(self._registers.PC, 0, 1)
            if (self._registers.PC & 0xFF00) != (self._temp_address & 0xFF00):
                self._cycle_number = 2
            else:
                self._current_instruction = &self.load_op_code
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &self.load_op_code

    cdef void BCS(self):
        if not self._cycle_number:
            self._branch_offset = self._memory_bus.execute(self._temp_address, 0, 1)
            if not (self._registers.P & CARRY_FLAG):
                # Branch not taken
                self._current_instruction = NULL
            else:
                self._temp_address += self._branch_offset + 1
                self._cycle_number = 1
            return

        if self._cycle_number == 1:
            self._registers.PC = (self._registers.PC & 0xFF00) | (self._temp_address & 0xFF)
            self._memory_bus.execute(self._registers.PC, 0, 1)
            if (self._registers.PC & 0xFF00) != (self._temp_address & 0xFF00):
                self._cycle_number = 2
            else:
                self._current_instruction = &self.load_op_code
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &self.load_op_code

    cdef void BEQ(self):
        if not self._cycle_number:
            self._branch_offset = self._memory_bus.execute(self._temp_address, 0, 1)
            if not (self._registers.P & ZERO_FLAG):
                # Branch not taken
                self._current_instruction = NULL
            else:
                self._temp_address += self._branch_offset + 1
                self._cycle_number = 1
            return

        if self._cycle_number == 1:
            self._registers.PC = (self._registers.PC & 0xFF00) | (self._temp_address & 0xFF)
            self._memory_bus.execute(self._registers.PC, 0, 1)
            if (self._registers.PC & 0xFF00) != (self._temp_address & 0xFF00):
                self._cycle_number = 2
            else:
                self._current_instruction = &self.load_op_code
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &self.load_op_code

    cdef void BIT(self):
        self._temp_data = self._memory_bus.execute(self._temp_address, 0, 1) & self._registers.ACC
        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._temp_data
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._temp_data & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._registers.P = (
            self._registers.P & ~OVERFLOW_FLAG
            if self._temp_data & OVERFLOW_FLAG
            else self._registers.P | OVERFLOW_FLAG
        )

        self._current_instruction = NULL

    cdef void BMI(self):
        if not self._cycle_number:
            self._branch_offset = self._memory_bus.execute(self._temp_address, 0, 1)
            if not (self._registers.P & NEGATIVE_FLAG):
                # Branch not taken
                self._current_instruction = NULL
            else:
                self._temp_address += self._branch_offset + 1
                self._cycle_number = 1
            return

        if self._cycle_number == 1:
            self._registers.PC = (self._registers.PC & 0xFF00) | (self._temp_address & 0xFF)
            self._memory_bus.execute(self._registers.PC, 0, 1)
            if (self._registers.PC & 0xFF00) != (self._temp_address & 0xFF00):
                self._cycle_number = 2
            else:
                self._current_instruction = &self.load_op_code
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &self.load_op_code

    cdef void BNE(self):
        if not self._cycle_number:
            self._branch_offset = self._memory_bus.execute(self._temp_address, 0, 1)
            if (self._registers.P & ZERO_FLAG):
                # Branch not taken
                self._current_instruction = NULL
            else:
                self._temp_address += self._branch_offset + 1
                self._cycle_number = 1
            return

        if self._cycle_number == 1:
            self._registers.PC = (self._registers.PC & 0xFF00) | (self._temp_address & 0xFF)
            self._memory_bus.execute(self._registers.PC, 0, 1)
            if (self._registers.PC & 0xFF00) != (self._temp_address & 0xFF00):
                self._cycle_number = 2
            else:
                self._current_instruction = &self.load_op_code
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &self.load_op_code

    cdef void BPL(self):
        if not self._cycle_number:
            self._branch_offset = self._memory_bus.execute(self._temp_address, 0, 1)
            if (self._registers.P & NEGATIVE_FLAG):
                # Branch not taken
                self._current_instruction = NULL
            else:
                self._temp_address += self._branch_offset + 1
                self._cycle_number = 1
            return

        if self._cycle_number == 1:
            self._registers.PC = (self._registers.PC & 0xFF00) | (self._temp_address & 0xFF)
            self._memory_bus.execute(self._registers.PC, 0, 1)
            if (self._registers.PC & 0xFF00) != (self._temp_address & 0xFF00):
                self._cycle_number = 2
            else:
                self._current_instruction = &self.load_op_code
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &self.load_op_code

    # cdef void BRK(self):
    #     pass

    cdef void BVC(self):
        if not self._cycle_number:
            self._branch_offset = self._memory_bus.execute(self._temp_address, 0, 1)
            if (self._registers.P & OVERFLOW_FLAG):
                # Branch not taken
                self._current_instruction = NULL
            else:
                self._temp_address += self._branch_offset + 1
                self._cycle_number = 1
            return

        if self._cycle_number == 1:
            self._registers.PC = (self._registers.PC & 0xFF00) | (self._temp_address & 0xFF)
            self._memory_bus.execute(self._registers.PC, 0, 1)
            if (self._registers.PC & 0xFF00) != (self._temp_address & 0xFF00):
                self._cycle_number = 2
            else:
                self._current_instruction = &self.load_op_code
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &self.load_op_code

    cdef void BVS(self):
        if not self._cycle_number:
            self._branch_offset = self._memory_bus.execute(self._temp_address, 0, 1)
            if not (self._registers.P & OVERFLOW_FLAG):
                # Branch not taken
                self._current_instruction = NULL
            else:
                self._temp_address += self._branch_offset + 1
                self._cycle_number = 1
            return

        if self._cycle_number == 1:
            self._registers.PC = (self._registers.PC & 0xFF00) | (self._temp_address & 0xFF)
            self._memory_bus.execute(self._registers.PC, 0, 1)
            if (self._registers.PC & 0xFF00) != (self._temp_address & 0xFF00):
                self._cycle_number = 2
            else:
                self._current_instruction = &self.load_op_code
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &self.load_op_code

    cdef void CLC(self):
        self._registers.P &= ~CARRY_FLAG
        self._current_instruction = NULL

    # cdef void CLD(self):
    #     self.clear_decimal_mode()
    #     self._current_instruction = NULL

    cdef void CLI(self):
        self._registers.P &= ~IRQ_DISABLE_FLAG
        self._current_instruction = NULL

    cdef void CLV(self):
        self._registers.P &= ~OVERFLOW_FLAG
        self._current_instruction = NULL

    cdef void CMP(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
            self._page_cross_possible = False
            return

        # Convert to 2's complement to subtract
        self._temp_data = (self._memory_bus.execute(self._temp_address, 0, 1) ^ 0xFF) + 1
        self._arithmetic_result = self._registers.ACC + self._temp_data

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if (self._arithmetic_result & 0xFF)
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if (self._arithmetic_result & 0x80)
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._registers.P = (
            self._registers.P | CARRY_FLAG
            if (self._arithmetic_result >> 8)
            else self._registers.P & ~CARRY_FLAG
        )

        self._current_instruction = NULL

    cdef void CPX(self):
        # Convert to 2's complement to subtract
        self._temp_data = (self._memory_bus.execute(self._temp_address, 0, 1) ^ 0xFF) + 1
        self._arithmetic_result = self._registers.X + self._temp_data

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if (self._arithmetic_result & 0xFF)
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if (self._arithmetic_result & 0x80)
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._registers.P = (
            self._registers.P | CARRY_FLAG
            if (self._arithmetic_result >> 8)
            else self._registers.P & ~CARRY_FLAG
        )

        self._current_instruction = NULL

    cdef void CPY(self):
        # Convert to 2's complement to subtract
        self._temp_data = (self._memory_bus.execute(self._temp_address, 0, 1) ^ 0xFF) + 1
        self._arithmetic_result = self._registers.Y + self._temp_data

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if (self._arithmetic_result & 0xFF)
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if (self._arithmetic_result & 0x80)
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._registers.P = (
            self._registers.P | CARRY_FLAG
            if (self._arithmetic_result >> 8)
            else self._registers.P & ~CARRY_FLAG
        )

        self._current_instruction = NULL

    cdef void SEC(self):
        self._registers.P |= CARRY_FLAG
        self._current_instruction = NULL

    # cdef void SED(self):
    #     self.set_decimal_mode()
    #     self._current_instruction = NULL

    cdef void SEI(self):
        self._registers.P |= IRQ_DISABLE_FLAG
        self._current_instruction = NULL

    ###
    #   GETTERS AND SETTERS
    ###
    cpdef Registers get_registers(self):
        return self._registers

    cpdef void set_registers(self, Registers registers):
        self._registers = registers
