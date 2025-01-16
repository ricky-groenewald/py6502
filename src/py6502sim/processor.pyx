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
DEF BREAK_FLAG = 0b00010000
DEF UNUSED_FLAG = 0b00100000
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
    
    def __init__(self) -> None:
        # Initialize internal and external variables
        self._memory_bus = None
        self._cycle_number = 0x00
        self._temp_data = 0x00
        self._temp_address = 0x0000
        self._page_cross_possible = False
        self._page_cross_occurred = False
        self._accumulator_addressing = False
        self._arithmetic_result = 0x0000
        self._branch_offset = 0x00
        self._decimal_mode_was_set = False

        # Initialize registers with RESET values
        self._registers.OPCODE = 0x00
        self._registers.INTERRUPT_TYPE = 0x00 # 0 = None/BRK, 1 = IRQ, 2 = RESET, 3 = NMI
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
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment
        self._next_instruction = NULL

        # Define OPCODE instruction functions
        # Format:
        #   self._instructions[OPCODE] = [Addressing Mode Function, OPCODE Function]
        #     or
        #   self._instructions[OPCODE] = [Special OPCODE Function, NULL] (BRK and JSR)
        # Invalid OPCODEs are set to [NULL, NULL]

        # 0x00 - 0x0F
        self._instructions[0x00][:] = [&MOS6502.BRK, NULL]
        self._instructions[0x01][:] = [&MOS6502.indirect_x, &MOS6502.ORA]
        self._instructions[0x05][:] = [&MOS6502.zero_page, &MOS6502.ORA]
        self._instructions[0x06][:] = [&MOS6502.zero_page, &MOS6502.ASL]
        self._instructions[0x08][:] = [&MOS6502.implied, &MOS6502.PHP]
        self._instructions[0x09][:] = [&MOS6502.immediate, &MOS6502.ORA]
        self._instructions[0x0A][:] = [&MOS6502.accumulator, &MOS6502.ASL]
        self._instructions[0x0D][:] = [&MOS6502.absolute, &MOS6502.ORA]
        self._instructions[0x0E][:] = [&MOS6502.absolute, &MOS6502.ASL]

        # 0x10 - 0x1F
        self._instructions[0x10][:] = [&MOS6502.immediate, &MOS6502.BPL]
        self._instructions[0x11][:] = [&MOS6502.indirect_y, &MOS6502.ORA]
        self._instructions[0x15][:] = [&MOS6502.zero_page_x, &MOS6502.ORA]
        self._instructions[0x16][:] = [&MOS6502.zero_page_x, &MOS6502.ASL]
        self._instructions[0x18][:] = [&MOS6502.implied, &MOS6502.CLC]
        self._instructions[0x19][:] = [&MOS6502.absolute_y, &MOS6502.ORA]
        self._instructions[0x1D][:] = [&MOS6502.absolute_x, &MOS6502.ORA]
        self._instructions[0x1E][:] = [&MOS6502.absolute_x, &MOS6502.ASL]

        # 0x20 - 0x2F
        self._instructions[0x20][:] = [&MOS6502.JSR, NULL]
        self._instructions[0x21][:] = [&MOS6502.indirect_x, &MOS6502.AND]
        self._instructions[0x24][:] = [&MOS6502.zero_page, &MOS6502.BIT]
        self._instructions[0x25][:] = [&MOS6502.zero_page, &MOS6502.AND]
        self._instructions[0x26][:] = [&MOS6502.zero_page, &MOS6502.ROL]
        self._instructions[0x28][:] = [&MOS6502.implied, &MOS6502.PLP]
        self._instructions[0x29][:] = [&MOS6502.immediate, &MOS6502.AND]
        self._instructions[0x2A][:] = [&MOS6502.accumulator, &MOS6502.ROL]
        self._instructions[0x2C][:] = [&MOS6502.absolute, &MOS6502.BIT]
        self._instructions[0x2D][:] = [&MOS6502.absolute, &MOS6502.AND]
        self._instructions[0x2E][:] = [&MOS6502.absolute, &MOS6502.ROL]

        # 0x30 - 0x3F
        self._instructions[0x30][:] = [&MOS6502.immediate, &MOS6502.BMI]
        self._instructions[0x31][:] = [&MOS6502.indirect_y, &MOS6502.AND]
        self._instructions[0x35][:] = [&MOS6502.zero_page_x, &MOS6502.AND]
        self._instructions[0x36][:] = [&MOS6502.zero_page_x, &MOS6502.ROL]
        self._instructions[0x38][:] = [&MOS6502.implied, &MOS6502.SEC]
        self._instructions[0x39][:] = [&MOS6502.absolute_y, &MOS6502.AND]
        self._instructions[0x3D][:] = [&MOS6502.absolute_x, &MOS6502.AND]
        self._instructions[0x3E][:] = [&MOS6502.absolute_x, &MOS6502.ROL]

        # 0x40 - 0x4F
        self._instructions[0x40][:] = [&MOS6502.implied, &MOS6502.RTI]
        self._instructions[0x41][:] = [&MOS6502.indirect_x, &MOS6502.EOR]
        self._instructions[0x45][:] = [&MOS6502.zero_page, &MOS6502.EOR]
        self._instructions[0x46][:] = [&MOS6502.zero_page, &MOS6502.LSR]
        self._instructions[0x48][:] = [&MOS6502.implied, &MOS6502.PHA]
        self._instructions[0x49][:] = [&MOS6502.immediate, &MOS6502.EOR]
        self._instructions[0x4A][:] = [&MOS6502.accumulator, &MOS6502.LSR]
        self._instructions[0x4C][:] = [&MOS6502.absolute, &MOS6502.JMP]
        self._instructions[0x4D][:] = [&MOS6502.absolute, &MOS6502.EOR]
        self._instructions[0x4E][:] = [&MOS6502.absolute, &MOS6502.LSR]

        # 0x50 - 0x5F
        self._instructions[0x50][:] = [&MOS6502.immediate, &MOS6502.BVC]
        self._instructions[0x51][:] = [&MOS6502.indirect_y, &MOS6502.EOR]
        self._instructions[0x55][:] = [&MOS6502.zero_page_x, &MOS6502.EOR]
        self._instructions[0x56][:] = [&MOS6502.zero_page_x, &MOS6502.LSR]
        self._instructions[0x58][:] = [&MOS6502.implied, &MOS6502.CLI]
        self._instructions[0x59][:] = [&MOS6502.absolute_y, &MOS6502.EOR]
        self._instructions[0x5D][:] = [&MOS6502.absolute_x, &MOS6502.EOR]
        self._instructions[0x5E][:] = [&MOS6502.absolute_x, &MOS6502.LSR]

        # 0x60 - 0x6F
        self._instructions[0x60][:] = [&MOS6502.implied, &MOS6502.RTS]
        self._instructions[0x61][:] = [&MOS6502.indirect_x, &MOS6502.ADC_SBC]
        self._instructions[0x65][:] = [&MOS6502.zero_page, &MOS6502.ADC_SBC]
        self._instructions[0x66][:] = [&MOS6502.zero_page, &MOS6502.ROR]
        self._instructions[0x68][:] = [&MOS6502.implied, &MOS6502.PLA]
        self._instructions[0x69][:] = [&MOS6502.immediate, &MOS6502.ADC_SBC]
        self._instructions[0x6A][:] = [&MOS6502.accumulator, &MOS6502.ROR]
        self._instructions[0x6C][:] = [&MOS6502.indirect, &MOS6502.JMP]
        self._instructions[0x6D][:] = [&MOS6502.absolute, &MOS6502.ADC_SBC]
        self._instructions[0x6E][:] = [&MOS6502.absolute, &MOS6502.ROR]

        # 0x70 - 0x7F
        self._instructions[0x70][:] = [&MOS6502.immediate, &MOS6502.BVS]
        self._instructions[0x71][:] = [&MOS6502.indirect_y, &MOS6502.ADC_SBC]
        self._instructions[0x75][:] = [&MOS6502.zero_page_x, &MOS6502.ADC_SBC]
        self._instructions[0x76][:] = [&MOS6502.zero_page_x, &MOS6502.ROR]
        self._instructions[0x78][:] = [&MOS6502.implied, &MOS6502.SEI]
        self._instructions[0x79][:] = [&MOS6502.absolute_y, &MOS6502.ADC_SBC]
        self._instructions[0x7D][:] = [&MOS6502.absolute_x, &MOS6502.ADC_SBC]
        self._instructions[0x7E][:] = [&MOS6502.absolute_x, &MOS6502.ROR]

        # 0x80 - 0x8F
        self._instructions[0x81][:] = [&MOS6502.indirect_x, &MOS6502.STA]
        self._instructions[0x84][:] = [&MOS6502.zero_page, &MOS6502.STY]
        self._instructions[0x85][:] = [&MOS6502.zero_page, &MOS6502.STA]
        self._instructions[0x86][:] = [&MOS6502.zero_page, &MOS6502.STX]
        self._instructions[0x88][:] = [&MOS6502.implied, &MOS6502.DEY]
        self._instructions[0x8A][:] = [&MOS6502.implied, &MOS6502.TXA]
        self._instructions[0x8C][:] = [&MOS6502.absolute, &MOS6502.STY]
        self._instructions[0x8D][:] = [&MOS6502.absolute, &MOS6502.STA]
        self._instructions[0x8E][:] = [&MOS6502.absolute, &MOS6502.STX]

        # 0x90 - 0x9F
        self._instructions[0x90][:] = [&MOS6502.immediate, &MOS6502.BCC]
        self._instructions[0x91][:] = [&MOS6502.indirect_y, &MOS6502.STA]
        self._instructions[0x94][:] = [&MOS6502.zero_page_x, &MOS6502.STY]
        self._instructions[0x95][:] = [&MOS6502.zero_page_x, &MOS6502.STA]
        self._instructions[0x96][:] = [&MOS6502.zero_page_y, &MOS6502.STX]
        self._instructions[0x98][:] = [&MOS6502.implied, &MOS6502.TYA]
        self._instructions[0x99][:] = [&MOS6502.absolute_y, &MOS6502.STA]
        self._instructions[0x9A][:] = [&MOS6502.implied, &MOS6502.TXS]
        self._instructions[0x9D][:] = [&MOS6502.absolute_x, &MOS6502.STA]

        # 0xA0 - 0xAF
        self._instructions[0xA0][:] = [&MOS6502.immediate, &MOS6502.LDY]
        self._instructions[0xA1][:] = [&MOS6502.indirect_x, &MOS6502.LDA]
        self._instructions[0xA2][:] = [&MOS6502.immediate, &MOS6502.LDX]
        self._instructions[0xA4][:] = [&MOS6502.zero_page, &MOS6502.LDY]
        self._instructions[0xA5][:] = [&MOS6502.zero_page, &MOS6502.LDA]
        self._instructions[0xA6][:] = [&MOS6502.zero_page, &MOS6502.LDX]
        self._instructions[0xA8][:] = [&MOS6502.implied, &MOS6502.TAY]
        self._instructions[0xA9][:] = [&MOS6502.immediate, &MOS6502.LDA]
        self._instructions[0xAA][:] = [&MOS6502.implied, &MOS6502.TAX]
        self._instructions[0xAC][:] = [&MOS6502.absolute, &MOS6502.LDY]
        self._instructions[0xAD][:] = [&MOS6502.absolute, &MOS6502.LDA]
        self._instructions[0xAE][:] = [&MOS6502.absolute, &MOS6502.LDX]

        # 0xB0 - 0xBF
        self._instructions[0xB0][:] = [&MOS6502.immediate, &MOS6502.BCS]
        self._instructions[0xB1][:] = [&MOS6502.indirect_y, &MOS6502.LDA]
        self._instructions[0xB4][:] = [&MOS6502.zero_page_x, &MOS6502.LDY]
        self._instructions[0xB5][:] = [&MOS6502.zero_page_x, &MOS6502.LDA]
        self._instructions[0xB6][:] = [&MOS6502.zero_page_y, &MOS6502.LDX]
        self._instructions[0xB8][:] = [&MOS6502.implied, &MOS6502.CLV]
        self._instructions[0xB9][:] = [&MOS6502.absolute_y, &MOS6502.LDA]
        self._instructions[0xBA][:] = [&MOS6502.implied, &MOS6502.TSX]
        self._instructions[0xBC][:] = [&MOS6502.absolute_x, &MOS6502.LDY]
        self._instructions[0xBD][:] = [&MOS6502.absolute_x, &MOS6502.LDA]
        self._instructions[0xBE][:] = [&MOS6502.absolute_y, &MOS6502.LDX]

        # 0xC0 - 0xCF
        self._instructions[0xC0][:] = [&MOS6502.immediate, &MOS6502.CPY]
        self._instructions[0xC1][:] = [&MOS6502.indirect_x, &MOS6502.CMP]
        self._instructions[0xC4][:] = [&MOS6502.zero_page, &MOS6502.CPY]
        self._instructions[0xC5][:] = [&MOS6502.zero_page, &MOS6502.CMP]
        self._instructions[0xC6][:] = [&MOS6502.zero_page, &MOS6502.DEC]
        self._instructions[0xC8][:] = [&MOS6502.implied, &MOS6502.INY]
        self._instructions[0xC9][:] = [&MOS6502.immediate, &MOS6502.CMP]
        self._instructions[0xCA][:] = [&MOS6502.implied, &MOS6502.DEX]
        self._instructions[0xCC][:] = [&MOS6502.absolute, &MOS6502.CPY]
        self._instructions[0xCD][:] = [&MOS6502.absolute, &MOS6502.CMP]
        self._instructions[0xCE][:] = [&MOS6502.absolute, &MOS6502.DEC]

        # 0xD0 - 0xDF
        self._instructions[0xD0][:] = [&MOS6502.immediate, &MOS6502.BNE]
        self._instructions[0xD1][:] = [&MOS6502.indirect_y, &MOS6502.CMP]
        self._instructions[0xD5][:] = [&MOS6502.zero_page_x, &MOS6502.CMP]
        self._instructions[0xD6][:] = [&MOS6502.zero_page_x, &MOS6502.DEC]
        self._instructions[0xD8][:] = [&MOS6502.implied, &MOS6502.CLD]
        self._instructions[0xD9][:] = [&MOS6502.absolute_y, &MOS6502.CMP]
        self._instructions[0xDD][:] = [&MOS6502.absolute_x, &MOS6502.CMP]
        self._instructions[0xDE][:] = [&MOS6502.absolute_x, &MOS6502.DEC]

        # 0xE0 - 0xEF
        self._instructions[0xE0][:] = [&MOS6502.immediate, &MOS6502.CPX]
        self._instructions[0xE1][:] = [&MOS6502.indirect_x, &MOS6502.ADC_SBC]
        self._instructions[0xE4][:] = [&MOS6502.zero_page, &MOS6502.CPX]
        self._instructions[0xE5][:] = [&MOS6502.zero_page, &MOS6502.ADC_SBC]
        self._instructions[0xE6][:] = [&MOS6502.zero_page, &MOS6502.INC]
        self._instructions[0xE8][:] = [&MOS6502.implied, &MOS6502.INX]
        self._instructions[0xE9][:] = [&MOS6502.immediate, &MOS6502.ADC_SBC]
        self._instructions[0xEA][:] = [&MOS6502.implied, &MOS6502.NOP]
        self._instructions[0xEC][:] = [&MOS6502.absolute, &MOS6502.CPX]
        self._instructions[0xED][:] = [&MOS6502.absolute, &MOS6502.ADC_SBC]
        self._instructions[0xEE][:] = [&MOS6502.absolute, &MOS6502.INC]

        # 0xF0 - 0xFF
        self._instructions[0xF0][:] = [&MOS6502.immediate, &MOS6502.BEQ]
        self._instructions[0xF1][:] = [&MOS6502.indirect_y, &MOS6502.ADC_SBC]
        self._instructions[0xF5][:] = [&MOS6502.zero_page_x, &MOS6502.ADC_SBC]
        self._instructions[0xF6][:] = [&MOS6502.zero_page_x, &MOS6502.INC]
        self._instructions[0xF8][:] = [&MOS6502.implied, &MOS6502.SED]
        self._instructions[0xF9][:] = [&MOS6502.absolute_y, &MOS6502.ADC_SBC]
        self._instructions[0xFD][:] = [&MOS6502.absolute_x, &MOS6502.ADC_SBC]
        self._instructions[0xFE][:] = [&MOS6502.absolute_x, &MOS6502.INC]

    ###
    #   GETTERS AND SETTERS
    ###
    cdef Registers get_registers(self):
        return self._registers

    cdef void set_registers(self, Registers registers):
        self._registers = registers

    def set_memory_bus(self, Component memory_bus):
        self._memory_bus = memory_bus

    ###
    #   CONTROL FUNCTIONS
    ###
    cdef void clock(self):
        if self._current_instruction:
            self._current_instruction(self)
        else:
            # Always increment PC if no instruction is loaded
            self._registers.PC += 1
            self.load_op_code()

    cdef void send_reset(self):
        # Stop everthing and reset the processor
        self._registers.INTERRUPT_TYPE = 2
        self._cycle_number = 0
        self._current_instruction = &MOS6502.load_op_code
        self._next_instruction = NULL

    cdef void send_irq(self):
        # IRQ fails if IRQ_DISABLE_FLAG is set
        if self._registers.P & IRQ_DISABLE_FLAG:
            return

        # IRQ can only interrupt BRK mid-cycle (TYPE = 0), and only if it's the first cycle after OPCODE read
        if self._current_instruction == &MOS6502.BRK and self._registers.INTERRUPT_TYPE == 0 and self._cycle_number == 0:
            self._registers.INTERRUPT_TYPE = 1
        elif not (self._current_instruction == &MOS6502.BRK or self._registers.INTERRUPT_TYPE):
            self._registers.INTERRUPT_TYPE = 1

    cdef void send_nmi(self):
        # Cannot interrupt RESETS
        if self._registers.INTERRUPT_TYPE == 2:
            return

        # NMI can only interrupt BRK mid-cycle (TYPE = 0), and only if it's the first cycle after OPCODE read
        if self._current_instruction == &MOS6502.BRK and self._registers.INTERRUPT_TYPE == 0 and self._cycle_number == 0:
            self._registers.INTERRUPT_TYPE = 3

        # In any other mid-cycle BRK type after the first cycle, queue another NMI break
        elif self._current_instruction == &MOS6502.BRK: # Not RESET
            self._next_instruction = &MOS6502.BRK

        # In all other cases, load the NMI interrupt regardless of current instruction or interrupt type
        else:
            self._registers.INTERRUPT_TYPE = 3

    cdef void load_op_code(self) except *:
        if self._registers.INTERRUPT_TYPE:
            self._registers.OPCODE = 0x00
            self._memory_bus.execute(self._registers.PC, 0, 1)
            self._current_instruction, self._next_instruction = &MOS6502.BRK, NULL
        else:
            self._registers.OPCODE = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._current_instruction = self._instructions[self._registers.OPCODE][0]
            self._next_instruction = self._instructions[self._registers.OPCODE][1]
            if self._current_instruction is NULL:
                raise InvalidOPCode(f'Invalid OPCODE: 0x{self._registers.OPCODE:02X}')

        self._cycle_number = 0
        # We don't update the PC here, as we need to keep the registers consistent
        # with its value during the entire cycle

    cdef void clear_bcd_opcodes(self):
        # Change all ADC and SBC opcodes back to normal
        # For NES implementations, remove this FOR loop
        for opcode in [
                0x69, 0x6D, 0x65, 0x61, 0x71, 0x75, 0x7D, 0x79,
                0xE9, 0xED, 0xE5, 0xE1, 0xF1, 0xF5, 0xFD, 0xF9
            ]:
            self._instructions[opcode][1] = &MOS6502.ADC_SBC
        # pass

    cdef void set_bcd_opcodes(self):
        # Change all ADC and SBC opcodes to use BCD version
        # For NES implementations, remove this FOR loop
        for opcode in [
                0x69, 0x6D, 0x65, 0x61, 0x71, 0x75, 0x7D, 0x79,
                0xE9, 0xED, 0xE5, 0xE1, 0xF1, 0xF5, 0xFD, 0xF9
            ]:
            self._instructions[opcode][1] = &MOS6502.ADC_SBC_BCD
        # pass

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

    cdef void indirect(self):
        if not self._cycle_number:
            self._registers.PC += 1
            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1) # IAL
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._registers.PC += 1
            self._temp_address |= (self._memory_bus.execute(self._registers.PC, 0, 1) << 8) # IAH, IAL
            self._cycle_number = 2
        elif self._cycle_number == 2:
            self._temp_data = self._memory_bus.execute(self._temp_address, 0, 1) # ADL
            self._cycle_number = 3
        else:
            # Add 1 to the absolute address to get the high byte, but keep the page the same
            self._temp_address = (self._temp_address & 0xFF00) | ((self._temp_address + 1) & 0xFF) # Not a bug

            self._temp_address = (self._memory_bus.execute(self._temp_address, 0, 1) << 8) | self._temp_data # ADH, ADL
            self._current_instruction, self._next_instruction = self._next_instruction, NULL
            self._cycle_number = 0

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
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
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

    cdef void ADC_SBC_BCD(self):
        ###
        ### You know what? ...Fuck BCD!
        ###
        ### Yeah... I can't remember how I got to this, but it works. I think I found a psuedo-code
        ### algorithm for BCD addition/subtraction on the internet somewhere and adapted it in my
        ### first "Pure Python" implementation. Look up commit 1dd4fd8 in the repo for more details.
        ###
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
                return

        cdef signed short result, bin_result

        # _temp_data is used to store the value read from memory/accumulator/operand
        self._temp_data = self._memory_bus.execute(self._temp_address, 0, 1)

        # If OPCODE & 0x80 is set, we are subtracting
        result = (
                (self._registers.ACC & 0x0F) +
                (1 - 2 * ((self._registers.OPCODE & 0x80) >> 7)) * (self._temp_data & 0x0F) +
                (self._registers.P & CARRY_FLAG) - ((self._registers.OPCODE & 0x80) >> 7)
            )

        if (self._registers.OPCODE & 0x80): # If subtracting
            bin_result = self._registers.ACC + (self._temp_data^0xff) + (self._registers.P & CARRY_FLAG)

            self._registers.P = (
                self._registers.P & ~ZERO_FLAG
                if bin_result & 0xFF
                else self._registers.P | ZERO_FLAG
            )
            self._registers.P = (
                self._registers.P | NEGATIVE_FLAG
                if bin_result & NEGATIVE_FLAG
                else self._registers.P & ~NEGATIVE_FLAG
            )

            if result < 0:
                result = ((result - 0x06) & 0x0f) - 0x10
            result = (self._registers.ACC & 0xf0) - (self._temp_data & 0xf0) + result
            if result < 0:
                result -= 0x60
            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if result >= 0
                else self._registers.P & ~CARRY_FLAG
            )
            self._temp_data ^= 0xff
            self._registers.P = (
                self._registers.P | OVERFLOW_FLAG
                if ((self._registers.ACC^(bin_result & 0xff)) & (self._temp_data^(bin_result & 0xff)) & 0x80)
                else self._registers.P & ~OVERFLOW_FLAG
            )
            self._registers.ACC = result & 0xff
        else:
            self._registers.P = (
                self._registers.P & ~ZERO_FLAG
                if ((self._registers.ACC + self._temp_data + (self._registers.P & CARRY_FLAG)) & 0xff)
                else self._registers.P | ZERO_FLAG
            )
            if result >= 0x0a:
                result = ((result + 0x06) & 0x0f) + 0x10
            bin_result = (self._registers.ACC & 0xf0) + (self._temp_data & 0xf0) + result
            if bin_result >= 0xa0:
                bin_result += 0x60
            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if bin_result >= 0x100
                else self._registers.P & ~CARRY_FLAG
            )

            signed_acc = self._registers.ACC & 0xf0
            signed_acc = signed_acc - (256 * (signed_acc >> 7))
            signed_val = self._temp_data & 0xf0
            signed_val = signed_val - (256 * (signed_val >> 7))
            signed_result = signed_acc + signed_val + result
            self._registers.P = (
                self._registers.P | NEGATIVE_FLAG
                if signed_result & NEGATIVE_FLAG
                else self._registers.P & ~NEGATIVE_FLAG
            )
            self._registers.P = (
                self._registers.P | OVERFLOW_FLAG
                if signed_result < -128 or signed_result > 127
                else self._registers.P & ~OVERFLOW_FLAG
            )

            self._registers.ACC = bin_result & 0xff

        self._current_instruction = NULL

    cdef void AND(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
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
            self._current_instruction = &MOS6502.load_op_code # prevent PC increment
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
                self._current_instruction = &MOS6502.load_op_code # prevent PC increment
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

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
                self._current_instruction = &MOS6502.load_op_code # prevent PC increment
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

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
                self._current_instruction = &MOS6502.load_op_code # prevent PC increment
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void BIT(self):
        self._temp_data = self._memory_bus.execute(self._temp_address, 0, 1)
        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._temp_data & self._registers.ACC
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._temp_data & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._registers.P = (
            self._registers.P | OVERFLOW_FLAG
            if self._temp_data & OVERFLOW_FLAG
            else self._registers.P & ~OVERFLOW_FLAG
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
                self._current_instruction = &MOS6502.load_op_code # prevent PC increment
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

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
                self._current_instruction = &MOS6502.load_op_code # prevent PC increment
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

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
                self._current_instruction = &MOS6502.load_op_code # prevent PC increment
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void BRK(self):
        if not self._cycle_number:
            self._temp_data = 0x00
            if not self._registers.INTERRUPT_TYPE:
                self._temp_data = BREAK_FLAG # Only BRK set B flag to 1
                self._registers.PC += 1
            elif self._registers.INTERRUPT_TYPE == 2: # RESET
                self._registers.PC = 0x00FF
                self._registers.S = 0x00

            self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        elif self._cycle_number == 1:
            if not self._registers.INTERRUPT_TYPE:
                self._registers.PC += 1

            self._memory_bus.execute(
                0x100 | self._registers.S,
                self._registers.PC >> 8,
                1 if self._registers.INTERRUPT_TYPE == 2 else 0
            )
            self._registers.S -= 1
            self._cycle_number = 2
        elif self._cycle_number == 2:
            self._memory_bus.execute(
                0x100 | self._registers.S,
                self._registers.PC & 0xFF,
                1 if self._registers.INTERRUPT_TYPE == 2 else 0
            )
            self._registers.S -= 1
            self._cycle_number = 3
        elif self._cycle_number == 3:
            self._registers.P |= UNUSED_FLAG
            self._registers.P &= ~BREAK_FLAG
            self._memory_bus.execute(
                0x100 | self._registers.S,
                self._registers.P | self._temp_data,
                1 if self._registers.INTERRUPT_TYPE == 2 else 0
            )
            self._registers.S -= 1
            self._registers.P |= IRQ_DISABLE_FLAG | BREAK_FLAG
            # self._registers.P &= ~DECIMAL_MODE_FLAG # Original NMOS 6502 doesn't clear this flag
            self._cycle_number = 4
        elif self._cycle_number == 4:
            # Read ADL at 0xFFFE for IRQ/BRK, 0xFFFA for NMI, 0xFFFC for RESET
            self._registers.PC = 0xFFFE - (2 * (self._registers.INTERRUPT_TYPE - 1)) if self._registers.INTERRUPT_TYPE else 0xFFFE

            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 5
        elif self._cycle_number == 5:
            # Read ADH at 0xFFFF for IRQ/BRK, 0xFFFB for NMI, 0xFFFD for RESET
            self._registers.PC += 1
            self._temp_address |= self._memory_bus.execute(self._registers.PC, 0, 1) << 8
            self._cycle_number = 6
        else:
            self._registers.PC = self._temp_address
            if self._next_instruction: # In case an NMI interrupt occured mid-cycle
                self._registers.INTERRUPT_TYPE = 3
            else:
                self._registers.INTERRUPT_TYPE = 0
            self.load_op_code()

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
                self._current_instruction = &MOS6502.load_op_code # prevent PC increment
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

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
                self._current_instruction = &MOS6502.load_op_code # prevent PC increment
            return

        self._registers.PC = self._temp_address
        self._memory_bus.execute(self._registers.PC, 0, 1)
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void CLC(self):
        self._registers.P &= ~CARRY_FLAG
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void CLD(self):
        self._registers.P &= ~DECIMAL_MODE_FLAG
        self.clear_bcd_opcodes()
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void CLI(self):
        self._registers.P &= ~IRQ_DISABLE_FLAG
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void CLV(self):
        self._registers.P &= ~OVERFLOW_FLAG
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void CMP(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
                return

        # Convert to 2's complement to subtract
        self._temp_data = (self._memory_bus.execute(self._temp_address, 0, 1) ^ 0xFF)
        self._arithmetic_result = self._registers.ACC + self._temp_data + 1

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if (self._arithmetic_result & 0xFF)
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._arithmetic_result & NEGATIVE_FLAG
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
        self._temp_data = (self._memory_bus.execute(self._temp_address, 0, 1) ^ 0xFF)
        self._arithmetic_result = self._registers.X + self._temp_data + 1

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if (self._arithmetic_result & 0xFF)
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._arithmetic_result & NEGATIVE_FLAG
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
        self._temp_data = (self._memory_bus.execute(self._temp_address, 0, 1) ^ 0xFF)
        self._arithmetic_result = self._registers.Y + self._temp_data + 1

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if (self._arithmetic_result & 0xFF)
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._arithmetic_result & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._registers.P = (
            self._registers.P | CARRY_FLAG
            if (self._arithmetic_result >> 8)
            else self._registers.P & ~CARRY_FLAG
        )

        self._current_instruction = NULL

    cdef void DEC(self):
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
            self._temp_data -= 1

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

            self._memory_bus.execute(self._temp_address, self._temp_data, 0)
            self._current_instruction = NULL

    cdef void DEX(self):
        self._registers.X -= 1

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.X
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.X & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void DEY(self):
        self._registers.Y -= 1

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.Y
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.Y & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void EOR(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
                return

        self._registers.ACC ^= self._memory_bus.execute(self._temp_address, 0, 1)
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

    cdef void INC(self):
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
            self._temp_data += 1

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

            self._memory_bus.execute(self._temp_address, self._temp_data, 0)
            self._current_instruction = NULL

    cdef void INX(self):
        self._registers.X += 1

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.X
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.X & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void INY(self):
        self._registers.Y += 1

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.Y
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.Y & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void JMP(self):
        self._registers.PC = self._temp_address
        self.load_op_code()

    cdef void JSR(self):
        if not self._cycle_number:
            self._registers.PC += 1
            self._temp_address = self._memory_bus.execute(self._registers.PC, 0, 1)
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._registers.PC += 1
            self._memory_bus.execute(0x100 | self._registers.S, 0, 1)
            self._cycle_number = 2
        elif self._cycle_number == 2:
            self._memory_bus.execute(0x100 | self._registers.S, self._registers.PC >> 8, 0)
            self._registers.S -= 1
            self._cycle_number = 3
        elif self._cycle_number == 3:
            self._memory_bus.execute(0x100 | self._registers.S, self._registers.PC & 0xFF, 0)
            self._registers.S -= 1
            self._cycle_number = 4
        elif self._cycle_number == 4:
            self._temp_address |= (self._memory_bus.execute(self._registers.PC, 0, 1) << 8)
            self._cycle_number = 5
        else:
            self._registers.PC = self._temp_address
            self.load_op_code()

    cdef void LDA(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
                return

        self._registers.ACC = self._memory_bus.execute(self._temp_address, 0, 1)

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

    cdef void LDX(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
                return

        self._registers.X = self._memory_bus.execute(self._temp_address, 0, 1)

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.X
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.X & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._current_instruction = NULL

    cdef void LDY(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
                return

        self._registers.Y = self._memory_bus.execute(self._temp_address, 0, 1)

        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.Y
            else self._registers.P | ZERO_FLAG
        )

        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.Y & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )

        self._current_instruction = NULL

    cdef void LSR(self):
        if self._accumulator_addressing:
            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if self._registers.ACC & 0x01
                else self._registers.P & ~CARRY_FLAG
            )

            self._registers.ACC >>= 1

            self._registers.P = (
                self._registers.P & ~ZERO_FLAG
                if self._registers.ACC
                else self._registers.P | ZERO_FLAG
            )
            self._registers.P = self._registers.P & ~NEGATIVE_FLAG

            self._accumulator_addressing = False
            self._current_instruction = &MOS6502.load_op_code # prevent PC increment
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
                if self._temp_data & 0x01
                else self._registers.P & ~CARRY_FLAG
            )

            self._temp_data >>= 1
            self._memory_bus.execute(self._temp_address, self._temp_data, 0)

            self._registers.P = (
                self._registers.P & ~ZERO_FLAG
                if self._temp_data
                else self._registers.P | ZERO_FLAG
            )
            self._registers.P = self._registers.P & ~NEGATIVE_FLAG

            self._current_instruction = NULL

    cdef void NOP(self):
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void ORA(self):
        if self._page_cross_possible:
            # Run a discarding cycle if a page cross occured
            self._page_cross_possible = False
            if self._page_cross_occurred:
                self._memory_bus.execute(self._temp_address, 0, 1)
                self._page_cross_occurred = False
                return

        self._registers.ACC |= self._memory_bus.execute(self._temp_address, 0, 1)
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

    cdef void PHA(self):
        if not self._cycle_number:
            self._cycle_number = 1
        else:
            self._memory_bus.execute(0x100 | self._registers.S, self._registers.ACC, 0)
            self._registers.S -= 1
            self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void PHP(self):
        if not self._cycle_number:
            self._cycle_number = 1
        else:
            self._memory_bus.execute(0x100 | self._registers.S, self._registers.P | BREAK_FLAG | UNUSED_FLAG, 0)
            self._registers.S -= 1
            self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void PLA(self):
        if not self._cycle_number:
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._memory_bus.execute(0x100 | self._registers.S, 0, 1)
            self._cycle_number = 2
        else:
            self._registers.S += 1
            self._registers.ACC = self._memory_bus.execute(0x100 | self._registers.S, 0, 1)
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
            self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void PLP(self):
        if not self._cycle_number:
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._memory_bus.execute(0x100 | self._registers.S, 0, 1)
            self._cycle_number = 2
        else:
            self._decimal_mode_was_set = <bint>(self._registers.P & DECIMAL_MODE_FLAG)

            self._registers.S += 1
            self._registers.P = self._memory_bus.execute(0x100 | self._registers.S, 0, 1) | BREAK_FLAG | UNUSED_FLAG

            # Check if BCD operations need to be enabled or disabled if necessary
            if <bint>(self._registers.P & DECIMAL_MODE_FLAG) and not self._decimal_mode_was_set:
                self.set_bcd_opcodes()
            elif not <bint>(self._registers.P & DECIMAL_MODE_FLAG) and self._decimal_mode_was_set:
                self.clear_bcd_opcodes()

            self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void ROL(self):
        if self._accumulator_addressing:
            self._arithmetic_result = self._registers.P & CARRY_FLAG # Used to store original carry bit

            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if self._registers.ACC & 0x80
                else self._registers.P & ~CARRY_FLAG
            )

            self._registers.ACC = (self._registers.ACC << 1) | self._arithmetic_result

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

            self._accumulator_addressing = False
            self._current_instruction = &MOS6502.load_op_code # prevent PC increment
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
            self._arithmetic_result = self._registers.P & CARRY_FLAG # Used to store original carry bit

            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if self._temp_data & 0x80
                else self._registers.P & ~CARRY_FLAG
            )

            self._temp_data = (self._temp_data << 1) | self._arithmetic_result
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

    cdef void ROR(self):
        if self._accumulator_addressing:
            self._arithmetic_result = (self._registers.P & CARRY_FLAG) << 7 # Used to store original carry bit

            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if self._registers.ACC & 0x01
                else self._registers.P & ~CARRY_FLAG
            )

            self._registers.ACC = (self._registers.ACC >> 1) | self._arithmetic_result

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

            self._accumulator_addressing = False
            self._current_instruction = &MOS6502.load_op_code # prevent PC increment
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
            self._arithmetic_result = (self._registers.P & CARRY_FLAG) << 7 # Used to store original carry bit

            self._registers.P = (
                self._registers.P | CARRY_FLAG
                if self._temp_data & 0x01
                else self._registers.P & ~CARRY_FLAG
            )

            self._temp_data = (self._temp_data >> 1) | self._arithmetic_result
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

    cdef void RTI(self):
        if not self._cycle_number:
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._memory_bus.execute(0x100 | self._registers.S, 0, 1)
            self._cycle_number = 2
        elif self._cycle_number == 2:
            self._decimal_mode_was_set = <bint>(self._registers.P & DECIMAL_MODE_FLAG)

            self._registers.S += 1
            self._registers.P = self._memory_bus.execute(0x100 | self._registers.S, 0, 1) | BREAK_FLAG | UNUSED_FLAG

            # Check if BCD operations need to be enabled or disabled if necessary
            if <bint>(self._registers.P & DECIMAL_MODE_FLAG) and not self._decimal_mode_was_set:
                self.set_bcd_opcodes()
            elif not <bint>(self._registers.P & DECIMAL_MODE_FLAG) and self._decimal_mode_was_set:
                self.clear_bcd_opcodes()

            self._cycle_number = 3
        elif self._cycle_number == 3:
            self._registers.S += 1
            self._temp_data = self._memory_bus.execute(0x100 | self._registers.S, 0, 1)
            self._cycle_number = 4
        else:
            self._registers.S += 1
            self._registers.PC = (self._memory_bus.execute(0x100 | self._registers.S, 0, 1) << 8) | self._temp_data
            self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void RTS(self):
        if not self._cycle_number:
            self._cycle_number = 1
        elif self._cycle_number == 1:
            self._memory_bus.execute(0x100 | self._registers.S, 0, 1)
            self._cycle_number = 2
        elif self._cycle_number == 2:
            self._registers.S += 1
            self._temp_data = self._memory_bus.execute(0x100 | self._registers.S, 0, 1)
            self._cycle_number = 3
        elif self._cycle_number == 3:
            self._registers.S += 1
            self._registers.PC = (self._memory_bus.execute(0x100 | self._registers.S, 0, 1) << 8) | self._temp_data
            self._cycle_number = 4
        else:
            self._memory_bus.execute(self._registers.PC, 0, 1)
            self._current_instruction = NULL

    cdef void SEC(self):
        self._registers.P |= CARRY_FLAG
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void SED(self):
        self._registers.P |= DECIMAL_MODE_FLAG
        self.set_bcd_opcodes()
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void SEI(self):
        self._registers.P |= IRQ_DISABLE_FLAG
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void STA(self):
        if self._page_cross_possible:
            # Run a discarding cycle after any addressing mode where page cross was possible
            self._memory_bus.execute(self._temp_address, 0, 1)
            self._page_cross_occurred = False
            self._page_cross_possible = False
            return

        self._memory_bus.execute(self._temp_address, self._registers.ACC, 0)
        self._current_instruction = NULL

    cdef void STX(self):
        self._memory_bus.execute(self._temp_address, self._registers.X, 0)
        self._current_instruction = NULL

    cdef void STY(self):
        self._memory_bus.execute(self._temp_address, self._registers.Y, 0)
        self._current_instruction = NULL

    cdef void TAX(self):
        self._registers.X = self._registers.ACC
        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.X
            else self._registers.P | ZERO_FLAG
        )
        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.X & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void TAY(self):
        self._registers.Y = self._registers.ACC
        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.Y
            else self._registers.P | ZERO_FLAG
        )
        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.Y & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void TSX(self):
        self._registers.X = self._registers.S
        self._registers.P = (
            self._registers.P & ~ZERO_FLAG
            if self._registers.X
            else self._registers.P | ZERO_FLAG
        )
        self._registers.P = (
            self._registers.P | NEGATIVE_FLAG
            if self._registers.X & NEGATIVE_FLAG
            else self._registers.P & ~NEGATIVE_FLAG
        )
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void TXA(self):
        self._registers.ACC = self._registers.X
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
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void TXS(self):
        self._registers.S = self._registers.X
        # No flags are affected
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment

    cdef void TYA(self):
        self._registers.ACC = self._registers.Y
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
        self._current_instruction = &MOS6502.load_op_code # prevent PC increment
