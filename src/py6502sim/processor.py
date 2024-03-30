"""
Simulator definitions and functions for the main 6502 micro processor
"""
from py6502sim.component import Component

# TODO:
#   * [HIGH IMPORTANCE] Convert to Cython
#   * [HIGH IMPORTANCE] TESTING!!
#   * [FEATURE] Add 65c02 instructions
#   * [OPTIMIZATION] Remove verbosity and implement it in a different file
#   * [OPTIMIZATION] Add get functions for registers
#   * [OPTIMIZATION] Move stack PUSH/PULL commands to separate function?
#   * [OPTIMIZATION] Better solution than "no_skip"?
#   * [MISSING] Rewrite docstrings to reflect all cases of returns (e.g. step function + verbose)

# Register List Offset Constants
ACC = 0
X = 1
Y = 2
PCL = 3
PCH = 4
S = 5
P = 6

class MOS6502:
    """
    Class definition for the main MOS 6502 processor

    Based on the 1976 revision of the MCS6502 processor
    """
    def __init__(self, memory: Component, verbosity: int) -> None:
        self._memory = memory
        self._current_data = 0
        self._current_address = 0
        self._write_buffer = []
        self._micro_cycle_counter = 0
        self._verbose = verbosity

        # Cycle log will contain a list of tuples in the form:
        # (
        #     micro-instruction description,
        #     address,
        #     data,
        #     read / write,
        #     disassembled code as a string (FIRST MICRO-INSTRUCTION ONLY)
        #     clock cycles to complete instruction (FIRST MICRO-INSTRUCTIONS ONLY)
        # )
        self._cycle_log: list[list] = []

        self._registers: list[int] = [
            0,   # Accumulator
            0,   # Index Register X
            0,   # Index Register Y
            0,   # Program Counter Low-byte
            0,   # Program Counter High-byte

            0,   # Stack Pointer S
            # Stack Pointer S is always "zero-paged". The pointer is always technically a 9-bit
            # number where bit 9 is always "1" and the bits 1 - 8 provide the 8-bit address in the
            # stack. I.e. S always points to addresses in the range 0x0100 ~ 0x01FF. Our
            # implementation will treat S as 8-bit, and assume it is always offset to 0x01XX.

            0b00110100, # Processor Status Register P
            # Processor Status Register P is an 8-bit register that contains various flags:
            # Bit 0 - Carry (C)
            # Bit 1 - Zero (Z)
            # Bit 2 - IRQ Disable (I)
            # Bit 3 - Decimal Mode (D)
            # Bit 4 - BRK Command (B)
            # Bit 5 -
            # Bit 6 - Overflow (V)
            # Bit 7 - Negative (N)
        ]

        # This is easier to type and organize for a human
        # Just temporary and not meant to be an instance/class variable
        instructions = {
            # [ADC] Add Memory to Accumulator with Carry
            # [SBC] Subtract Memory From Accumulator with Borrow
            (
                0x69, 0x6D, 0x65, 0x61, 0x71, 0x75, 0x7D, 0x79,
                0xE9, 0xED, 0xE5, 0xE1, 0xF1, 0xF5, 0xFD, 0xF9
            ): (self._inst_adc_sbc, self._inst_adc_sbc_verbose),

            # [AND] "AND" Memory with Accumulator
            # [EOR] "XOR" Memory with Accumulator
            # [ORA] "OR" Memory with Accumulator
            (
                0x29, 0x2D, 0x25, 0x21, 0x31, 0x35, 0x3D, 0x39,
                0x49, 0x4D, 0x45, 0x41, 0x51, 0x55, 0x5D, 0x59,
                0x09, 0x0D, 0x05, 0x01, 0x11, 0x15, 0x1D, 0x19,
            ): (self._inst_logic, self._inst_logic_verbose),

            # [ASL] Arithmetic Shift Left by 1 Bit
            # [DEC] Decrement Memory by 1
            # [INC] Increment Memory by 1
            # [LSR] Logic Shift Right by 1 Bit
            # [ROL] Rotate 1 Bit Left
            # [ROR] Rotate 1 Bit Right
            (
                0x0E, 0x06, 0x0A, 0x16, 0x1E,
                0xCE, 0xC6,       0xD6, 0xDE,
                0xEE, 0xE6,       0xF6, 0xFE,
                0x4E, 0x46, 0x4A, 0x56, 0x5E,
                0x2E, 0x26, 0x2A, 0x36, 0x3E,
                0x6E, 0x66, 0x6A, 0x76, 0x7E
            ): (self._inst_read_mod_write, self._inst_read_mod_write_verbose),

            # [BIT] Test Bits in Memory with Accumulator
            (0x2C, 0x24): (self._inst_bit_test, self._inst_bit_test_verbose),

            # [BCC] Branch on Carry Clear
            # [BCS] Branch on Carry Set
            # [BEQ] Branch on Result Zero (Zero Set)
            # [BMI] Branch on Result Minus (Negative Set)
            # [BNE] Branch on Result Not Zero (Zero Clear)
            # [BPL] Branch on Result Plus (Negative Clear)
            # [BVC] Branch on Overflow Clear
            # [BVS] Branch on Overflow Set
            (
                0x90, 0xB0, 0xF0, 0x30, 0xD0, 0x10, 0x50, 0x70
            ): (self._inst_branch, self._inst_branch_verbose),

            # [BRK] Break Operation
            (0x00,): (self._inst_break, self._inst_break_verbose),

            # [CLC] Clear Carry Flag
            # [CLD] Clear Decimal Mode
            # [CLI] Clear Interrupt Disable Bit
            # [CLV] Clear Overflow Flag
            # [SEC] Set Carry Flag
            # [SED] Set Decimal Mode
            # [SEI] Set Interrupt Disable Bit
            (
                0x18, 0xD8, 0x58, 0xB8, 0x38, 0xF8, 0x78
            ): (self._inst_clear_set_flag, self._inst_clear_set_flag_verbose),

            # [CMP] Compare Memory and Accumulator
            # [CPX] Compare Memory and Index X
            # [CPY] Compare Memory and Index Y
            (
                0xC9, 0xCD, 0xC5, 0xC1, 0xD1, 0xD5, 0xDD, 0xD9,
                0xE0, 0xEC, 0xE4,
                0xC0, 0xCC, 0xC4,                              
            ): (self._inst_compare, self._inst_compare_verbose),

            # [DEX] Decrement X by 1
            # [DEY] Decrement Y by 1
            # [INX] Increment X by 1
            # [INY] Increment Y by 1
            (0xCA, 0x88, 0xE8, 0xC8): (self._inst_inc_dec_xy, self._inst_inc_dec_xy_verbose),

            # [JMP] Jump Operation
            (0x4C, 0x6C): (self._inst_jump, self._inst_jump_verbose),

            # [JSR] Jump to Subroutine
            (0x20,): (self._inst_jump_to_subroutine, self._inst_jump_to_subroutine_verbose),

            # [LDA] Load Accumulator with Memory
            # [LDX] Load Index X with Memory
            # [LDY] Load Index Y with Memory
            (
                0xA9, 0xAD, 0xA5, 0xA1, 0xB1, 0xB5, 0xBD, 0xB9,
                0xA2, 0xAE, 0xA6, 0xBE, 0xB6,
                0xA0, 0xAC, 0xA4, 0xB4, 0xBC                   
            ): (self._inst_load_from_memory, self._inst_load_from_memory_verbose),

            # [NOP] No Operation
            (0xEA,): (self._inst_nop, self._inst_nop_verbose),

            # [PHA] Push Accumulator on Stack
            # [PHP] Push Status Register on Stack
            # [PLA] Pull Accumulator from Stack
            # [PLP] Pull Status Register from Stack
            (
                0x48, 0x08, 0x68, 0x28
            ): (self._inst_push_pull_stack, self._inst_push_pull_stack_verbose),

            # [RTI] Return from Interrupt
            # [RTS] Return from Subroutine
            (0x40, 0x60): (self._inst_return, self._inst_return_verbose),

            # [STA] Store Accumulator in Memory
            # [STX] Store Index X in Memory
            # [STY] Store Index Y in Memory
            (
                0x8D, 0x85, 0x81, 0x91, 0x95, 0x9D, 0x99,
                0x8E, 0x86, 0x96,
                0x8C, 0x84, 0x94                         
            ): (self._inst_store_in_memory, self._inst_store_in_memory_verbose),

            # [TAX] Transfer Accumulator to Index X
            # [TAY] Transfer Accumulator to Index Y
            # [TSX] Transfer Stack Pointer to Index X
            # [TXA] Transfer Index X to Accumulator
            # [TXS] Transfer Index X to Stack Pointer
            # [TYA] Transfer Index Y to Accumulator
            (
                0xAA, 0xA8, 0xBA, 0x8A, 0x9A, 0x98
            ): (self._inst_transfer, self._inst_transfer_verbose),
        }

        # This is quicker to access through code for a computer
        self._instructions = [None] * 256
        instruction_gen = (
            (code, op[0]) for hex_list, op in instructions.items() for code in hex_list
        )
        for code, op in instruction_gen:
            self._instructions[code] = op

        self._verbose_instructions = [None] * 256
        instruction_gen = (
            (code, op[1]) for hex_list, op in instructions.items() for code in hex_list
        )
        for code, op in instruction_gen:
            self._verbose_instructions[code] = op

        # Build quick lookup table for addressing mode fetch/write functions
        self._addressing_modes = [None] * 0x1F
        for mode in (0x02, 0x09):
            self._addressing_modes[mode] = self._immediate_mode_fetch_write_data    # Immediate
            self._addressing_modes[0x10 | mode] = self._abs_y_mode_fetch_write_data # Absolute, Y

        for mode in (0x0C, 0x0D, 0x0E):
            self._addressing_modes[mode] = self._absolute_mode_fetch_write_data     # Absolute
            self._addressing_modes[0x10 | mode] = self._abs_x_mode_fetch_write_data # Absolute, X

        for mode in (0x04, 0x05, 0x06):
            self._addressing_modes[mode] = self._zero_page_mode_fetch_write_data    # Zero Page
            self._addressing_modes[0x10 | mode] = self._zp_x_mode_fetch_write_data  # Zero Page, X

        self._addressing_modes[0x0A] = self._accumulator_mode_fetch_write_data      # Accumulator
        self._addressing_modes[0x01] = self._ind_x_mode_fetch_write_data            # (Indirect, X)
        self._addressing_modes[0x11] = self._ind_y_mode_fetch_write_data            # (Indirect), Y

        self._verbose_addressing_modes = [None] * 0x1F
        for mode in (0x02, 0x09):
            self._verbose_addressing_modes[mode] = self._immediate_mode_fetch_write_data_verbose    # Immediate
            self._verbose_addressing_modes[0x10 | mode] = self._abs_y_mode_fetch_write_data_verbose # Absolute, Y

        for mode in (0x0C, 0x0D, 0x0E):
            self._verbose_addressing_modes[mode] = self._absolute_mode_fetch_write_data_verbose     # Absolute
            self._verbose_addressing_modes[0x10 | mode] = self._abs_x_mode_fetch_write_data_verbose # Absolute, X

        for mode in (0x04, 0x05, 0x06):
            self._verbose_addressing_modes[mode] = self._zero_page_mode_fetch_write_data_verbose    # Zero Page
            self._verbose_addressing_modes[0x10 | mode] = self._zp_x_mode_fetch_write_data_verbose  # Zero Page, X

        self._verbose_addressing_modes[0x0A] = self._accumulator_mode_fetch_write_data_verbose      # Accumulator
        self._verbose_addressing_modes[0x01] = self._ind_x_mode_fetch_write_data_verbose            # (Indirect, X)
        self._verbose_addressing_modes[0x11] = self._ind_y_mode_fetch_write_data_verbose            # (Indirect), Y

    """
    #    
    #    PUBLIC FACING CONTROL FUNCTIONS
    #    
    """
    def reset(self) -> None:
        """
        Run the processor through the reset sequence.
        """
        self._micro_cycle_counter = 0
        if not self._verbose:
            return self._inst_break(brk_type=3)

        self._cycle_log = []
        disasm_string, cycle_count = self._inst_break_verbose(brk_type=3)
        # Add the Disassembled Code and total number of cycles for current instruction to
        # the first cycle log.
        self._cycle_log[0].extend((disasm_string, cycle_count))

    def step(self) -> list:
        """
        Step through clock cycles.

        TODO: Rewrite docstring
        Returns:
            A list containing the following
                - Micro-instruction description
                - Address bus value
                - Data bus value
                - Read / Write
                - Disassembled code as a string (First micro-instructions only)
                - Number of clock cycles to complete instruction (First micro-instructions only)
        """
        # If verbosity level is 0, use non-verbose functions
        if not self._verbose:
            return self._instructions[self._read_next_program_byte()]()

        # If verbosity level == 1, the next instruction will be executed regardless whether
        # the output of all previous micro-instructions have been processed.
        # Rest assured: The function of the processor will not suffer if a mid-instruction
        # verbosity change has been made.
        if self._micro_cycle_counter == len(self._cycle_log) or self._verbose == 1:
            self._cycle_log = []
            self._micro_cycle_counter = 0

            # Add the Disassembled Code and total number of cycles for current instruction to
            # the first cycle log.
            disasm_string, cycle_count = self._verbose_instructions[
                self._read_next_program_byte_verbose(desc='Fetch OP CODE @ PC')
            ]()

            # Verbosity level is 1, return disassembled instruction and cycle count
            if self._verbose == 1:
                self._cycle_log = []
                return [disasm_string, cycle_count]

            self._cycle_log[0].extend((disasm_string, cycle_count))

        self._micro_cycle_counter += 1
        return self._cycle_log[self._micro_cycle_counter - 1]

    def set_verbosity_level(self, level: int) -> None:
        """
        Set the verbosity level of each step's output.

        Level 0:
            Instructions are completed in a single step and only the number of clock cycles the
            instruction took to complete is returned.

        Level 1:
            Instructions are completed in a single step and the disassembled instruction and the
            number of cycles the instruction to complete are returned.

        Level 2:
            Output will be generated on each clock cycle, providing the current micro-instruction
            that has been executed within the instruction. The disassembled instruction and number
            of cycles it is expected to take will be returned alongside the first micro-
            instruction.


        Arguments:
            level (int): Desired level of verbosity
        """
        if not isinstance(level, int) or not 0 <= level <= 2:
            raise ValueError(
                'Expected an int value of 1, 2, or 3 for verbosity level. '
                f'Received <{type(level)}> {level}'
            )

        self._verbose = level


    """
    #    
    #    FLAG GET AND SET FUNCTIONS
    #    
    """
    def _get_carry_flag(self) -> int:
        return self._registers[P] & 1

    def _get_zero_flag(self) -> int:
        return (self._registers[P] >> 1) & 1

    def _get_irq_disable_flag(self) -> int:
        return (self._registers[P] >> 2) & 1

    def _get_decimal_mode(self) -> int:
        return (self._registers[P] >> 3) & 1

    def _get_break_flag(self) -> int:
        return (self._registers[P] >> 4) & 1

    def _get_overflow_flag(self) -> int:
        return (self._registers[P] >> 6) & 1

    def _get_negative_flag(self) -> int:
        return (self._registers[P] >> 7) & 1

    def _set_carry_flag(self, value: bool):
        if value:
            self._registers[P] |= 0b1
        else:
            self._registers[P] &= 0b11111110

    def _set_zero_flag(self, value: bool):
        if value:
            self._registers[P] |= 0b10
        else:
            self._registers[P] &= 0b11111101

    def _set_irq_disable_flag(self, value: bool):
        if value:
            self._registers[P] |= 0b100
        else:
            self._registers[P] &= 0b11111011

    def _set_decimal_mode(self, value: bool):
        if value:
            self._registers[P] |= 0b1000
        else:
            self._registers[P] &= 0b11110111

    def _set_break_flag(self, value: bool):
        if value:
            self._registers[P] |= 0b10000
        else:
            self._registers[P] &= 0b11101111

    def _set_overflow_flag(self, value: bool):
        if value:
            self._registers[P] |= 0b1000000
        else:
            self._registers[P] &= 0b10111111

    def _set_negative_flag(self, value: bool):
        if value:
            self._registers[P] |= 0b10000000
        else:
            self._registers[P] &= 0b01111111

    """
    #    
    #    READ / WRITE FUNCTIONS
    #    
    """
    def _read_byte_from_current_address(self) -> int:
        self._current_data = self._memory.execute(self._current_address, self._current_data, 1)
        return self._current_data

    def _read_byte_from_current_address_verbose(self, *, desc: str) -> int:
        self._current_data = self._memory.execute(self._current_address, self._current_data, 1)
        self._cycle_log.append([
            desc,
            self._current_address,
            self._current_data,
            1,
        ])
        return self._current_data

    def _write_byte_to_current_address(self) -> int:
        self._current_data = self._memory.execute(self._current_address, self._current_data, 0)
        return self._current_data

    def _write_byte_to_current_address_verbose(self, *, desc: str) -> int:
        self._current_data = self._memory.execute(self._current_address, self._current_data, 0)
        self._cycle_log.append([
            desc,
            self._current_address,
            self._current_data,
            0,
        ])
        return self._current_data

    def _read_next_program_byte(self, *, advance: bool=True) -> int:
        # Advance is set false with Single Byte Instructions running for 2 clock cycles
        self._current_address = (self._registers[PCH] << 8) | self._registers[PCL]
        address = self._current_address + advance
        self._registers[PCL] = address & 0xff
        self._registers[PCH] = (address & 0xff00) >> 8
        return self._read_byte_from_current_address()

    def _read_next_program_byte_verbose(self, *, advance: bool=True, desc: str) -> int:
        # Advance is set false with Single Byte Instructions running for 2 clock cycles
        self._current_address = (self._registers[PCH] << 8) | self._registers[PCL]
        address = self._current_address + advance
        self._registers[PCL] = address & 0xff
        self._registers[PCH] = (address & 0xff00) >> 8
        return self._read_byte_from_current_address_verbose(desc=desc)

    def _stack_pull(self) -> int:
        self._registers[S] = (self._registers[S] + 1) & 0xff
        self._current_address = 0x0100 | self._registers[S]
        return self._read_byte_from_current_address()

    def _stack_pull_verbose(self, *, desc: str) -> int:
        self._registers[S] = (self._registers[S] + 1) & 0xff
        self._current_address = 0x0100 | self._registers[S]
        return self._read_byte_from_current_address_verbose(desc=desc)

    def _stack_push_current_data(self) -> None:
        self._current_address = 0x0100 | self._registers[S]
        self._write_byte_to_current_address()
        self._registers[S] = (self._registers[S] - 1) & 0xff

    def _stack_push_current_data_verbose(self, *, desc: str) -> None:
        self._current_address = 0x0100 | self._registers[S]
        self._write_byte_to_current_address_verbose(desc=desc)
        self._registers[S] = (self._registers[S] - 1) & 0xff

    """
    #    
    #    DATA FETCH/WRITE FUNCTIONS FOR VARIOUS ADDRESSING MODE 
    #    
    """
    #
    #    IMMEDIATE ADDRESSING MODE
    #
    def _immediate_mode_fetch_write_data(self, _no_skip: bool=False) -> tuple[int, int]:
        value = self._read_next_program_byte()
        return value, 2

    def _immediate_mode_fetch_write_data_verbose(self, _no_skip: bool=False)->tuple[int, int, str]:
        value = self._read_next_program_byte_verbose(desc='Fetch DATA @ PC + 1')
        return value, 2, f'#${value:02X}'

    #
    #    ABSOLUTE ADDRESSING MODE
    #
    def _absolute_mode_fetch_write_data(self, _no_skip: bool=False) -> tuple[int, int]:
        low_byte = self._read_next_program_byte()
        high_byte = self._read_next_program_byte()
        self._current_address = (high_byte << 8) | low_byte
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address(), 4
        return self._read_byte_from_current_address(), 4

    def _absolute_mode_fetch_write_data_verbose(self, _no_skip: bool=False) -> tuple[int, int, str]:
        low_byte = self._read_next_program_byte_verbose(
            desc='Fetch Effective Address low-byte (ADL) @ PC + 1'
        )
        high_byte = self._read_next_program_byte_verbose(
            desc='Fetch Effective Address high-byte (ADH) @ PC + 2'
        )
        self._current_address = (high_byte << 8) | low_byte
        disasm_operand = f'${self._current_address:04X}'
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address_verbose(
                desc='Write DATA @ (ADH, ADL)'
            ), 4, disasm_operand
        return self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (ADH, ADL)'
        ), 4, disasm_operand

    #
    #    ZERO PAGE ADDRESSING MODE
    #
    def _zero_page_mode_fetch_write_data(self, _no_skip: bool=False) -> tuple[int, int]:
        low_byte = self._read_next_program_byte()
        self._current_address = low_byte
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address(), 3
        return self._read_byte_from_current_address(), 3

    def _zero_page_mode_fetch_write_data_verbose(self, _no_skip: bool=False)->tuple[int, int, str]:
        low_byte = self._read_next_program_byte_verbose(
            desc='Fetch Zero-Page Effective Address (ADL) @ PC + 1'
        )
        self._current_address = low_byte
        disasm_operand = f'${low_byte:02X}'
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address_verbose(
                desc='Write DATA @ (00, ADL)'
            ), 3, disasm_operand
        return self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (00, ADL)'
        ), 3, disasm_operand

    #
    #    ACCUMULATOR ADDRESSING MODE
    #
    def _accumulator_mode_fetch_write_data(self, _no_skip: bool=False) -> tuple[int, int]:
        return self._registers[ACC], 2

    def _accumulator_mode_fetch_write_data_verbose(self, _no_skip: bool=False)->tuple[int,int,str]:
        return self._registers[ACC], 2, ''

    #
    #    ZERO PAGE (X) ADDRESSING MODE
    #
    def _zp_x_mode_fetch_write_data(self, _no_skip: bool=False) -> tuple[int, int]:
        self._current_address = self._read_next_program_byte()
        self._read_byte_from_current_address()
        self._current_address = (self._current_address + self._registers[X]) & 0xff
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address(), 4
        return self._read_byte_from_current_address(), 4

    def _zp_x_mode_fetch_write_data_verbose(self, _no_skip: bool=False) -> tuple[int, int, str]:
        self._current_address = self._read_next_program_byte_verbose(
            desc='Fetch Zero-Page Base Address (BAL) @ PC + 1'
        )
        self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (00, BAL) [DISCARDED]'
        )
        disasm_operand = f'${self._current_address:02X},X'
        self._current_address = (self._current_address + self._registers[X]) & 0xff
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address_verbose(
                desc='Write DATA @ (00, BAL + X)'
            ), 4, disasm_operand

        return self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (00, BAL + X)'
        ), 4, disasm_operand

    #
    #    ZERO PAGE (Y) ADDRESSING MODE
    #
    def _zp_y_mode_fetch_write_data(self, _no_skip: bool=False) -> tuple[int, int]:
        self._current_address = self._read_next_program_byte()
        self._read_byte_from_current_address()
        self._current_address = (self._current_address + self._registers[Y]) & 0xff
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address(), 4
        return self._read_byte_from_current_address(), 4

    def _zp_y_mode_fetch_write_data_verbose(self, _no_skip: bool=False) -> tuple[int, int, str]:
        self._current_address = self._read_next_program_byte_verbose(
            desc='Fetch Zero-Page Base Address (BAL) @ PC + 1'
        )
        self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (00, BAL) [DISCARDED]'
        )
        disasm_operand = f'${self._current_address:02X},Y'
        self._current_address = (self._current_address + self._registers[Y]) & 0xff
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address_verbose(
                desc='Write DATA @ (00, BAL + Y)'
            ), 4, disasm_operand

        return self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (00, BAL + Y)'
        ), 4, disasm_operand

    #
    #    ABSOLUTE (X) ADDRESSING MODE
    #
    def _abs_x_mode_fetch_write_data(self, no_skip: bool=False) -> tuple[int, int]:
        low_byte = self._read_next_program_byte() + self._registers[X]
        high_byte = self._read_next_program_byte()
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address()
        if no_skip or low_byte >> 8 or self._write_buffer:
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                return self._write_byte_to_current_address(), 5

            return self._read_byte_from_current_address(), 5

        return value, 4

    def _abs_x_mode_fetch_write_data_verbose(self, no_skip: bool=False) -> tuple[int, int, str]:
        low_byte = self._read_next_program_byte_verbose(
            desc='Fetch Base Address low-byte (BAL) @ PC + 1'
        ) + self._registers[X]
        high_byte = self._read_next_program_byte_verbose(
            desc='Fetch Base Address high-byte (BAH) @ PC + 2'
        )
        disasm_operand = f'${high_byte:02X}{low_byte-self._registers[X]:02X},X'
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (BAH, BAL + X)'
        ), 4, disasm_operand
        if no_skip or low_byte >> 8 or self._write_buffer:
            self._cycle_log[-1][0] = 'Fetch DATA @ (BAH, BAL + X) [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                value = self._write_byte_to_current_address_verbose(
                    desc='Write DATA @ (BAH + C, BAL + X)'
                ), 5, disasm_operand
            else:
                value = self._read_byte_from_current_address_verbose(
                    desc=(
                        'Fetch DATA @ (BAH + C, BAL + X)' if no_skip
                        else 'Fetch DATA @ (BAH + 1, BAL + X)'
                    )
                ), 5, disasm_operand

        return value

    #
    #    ABSOLUTE (Y) ADDRESSING MODE
    #
    def _abs_y_mode_fetch_write_data(self, no_skip: bool=False) -> tuple[int, int]:
        low_byte = self._read_next_program_byte() + self._registers[Y]
        high_byte = self._read_next_program_byte()
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address()
        if no_skip or low_byte >> 8 or self._write_buffer:
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                return self._write_byte_to_current_address(), 5

            return self._read_byte_from_current_address(), 5

        return value, 4

    def _abs_y_mode_fetch_write_data_verbose(self, no_skip: bool=False) -> tuple[int, int, str]:
        low_byte = self._read_next_program_byte_verbose(
            desc='Fetch Base Address low-byte (BAL) @ PC + 1'
        ) + self._registers[Y]
        high_byte = self._read_next_program_byte_verbose(
            desc='Fetch Base Address high-byte (BAH) @ PC + 2'
        )
        disasm_operand = f'${high_byte:02X}{low_byte-self._registers[Y]:02X},Y'
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (BAH, BAL + Y)'
        ), 4, disasm_operand
        if no_skip or low_byte >> 8 or self._write_buffer:
            self._cycle_log[-1][0] = 'Fetch DATA @ (BAH, BAL + Y) [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                value = self._write_byte_to_current_address_verbose(
                    desc='Write DATA @ (BAH + C, BAL + Y)'
                ), 5, disasm_operand
            else:
                value = self._read_byte_from_current_address_verbose(
                    desc=(
                        'Fetch DATA @ (BAH + C, BAL + Y)' if no_skip
                        else 'Fetch DATA @ (BAH + 1, BAL + Y)'
                    )
                ), 5, disasm_operand

        return value

    #
    #    INDEXED INDIRECT (X) ADDRESSING MODE
    #
    def _ind_x_mode_fetch_write_data(self, _no_skip: bool=False) -> tuple[int, int]:
        self._current_address = self._read_next_program_byte()
        self._read_byte_from_current_address()
        self._current_address = (self._current_address + self._registers[X]) & 0xff
        low_byte = self._read_byte_from_current_address()
        self._current_address = (self._current_address + 1) & 0xff
        high_byte = self._read_byte_from_current_address()
        self._current_address = (high_byte << 8) | low_byte
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address(), 6

        return self._read_byte_from_current_address(), 6

    def _ind_x_mode_fetch_write_data_verbose(self, _no_skip: bool=False) -> tuple[int, int, str]:
        self._current_address = self._read_next_program_byte_verbose(
            desc='Fetch Zero-Page Base Address (BAL) @ PC + 1'
        )
        disasm_operand = f'(${self._current_address:02X},X)'
        self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (00, BAL) [DISCARDED]'
        )
        self._current_address = (self._current_address + self._registers[X]) & 0xff
        low_byte = self._read_byte_from_current_address_verbose(
            desc='Fetch Effective Address low-byte (ADL) @ (00, BAL + X)'
        )
        self._current_address = (self._current_address + 1) & 0xff
        high_byte = self._read_byte_from_current_address_verbose(
            desc='Fetch Effective Address high-byte (ADH) @ (00, BAL + X + 1)'
        )
        self._current_address = (high_byte << 8) | low_byte
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address_verbose(
                desc='Write DATA @ (ADH, ADL)'
            ), 6, disasm_operand

        return self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (ADH, ADL)'
        ), 6, disasm_operand

    #
    #    INDIRECT INDEXED (Y) ADDRESSING MODE
    #
    def _ind_y_mode_fetch_write_data(self, _no_skip: bool=False) -> tuple[int, int]:
        self._current_address = self._read_next_program_byte()
        low_byte = self._read_byte_from_current_address() + self._registers[Y]
        self._current_address = (self._current_address + 1) & 0xff
        high_byte = self._read_byte_from_current_address()
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address()
        if low_byte >> 8 or self._write_buffer:
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                return self._write_byte_to_current_address(), 6

            return self._read_byte_from_current_address(), 6

        return value, 5

    def _ind_y_mode_fetch_write_data_verbose(self, _no_skip: bool=False) -> tuple[int, int, str]:
        self._current_address = self._read_next_program_byte_verbose(
            desc='Fetch Zero-Page Inderect Address (IAL) @ PC + 1'
        )
        disasm_operand = f'(${self._current_address:02X}),Y'
        low_byte = self._read_byte_from_current_address_verbose(
            desc='Fetch Base Address low-byte (BAL) @ (00, IAL)'
        ) + self._registers[Y]
        self._current_address = (self._current_address + 1) & 0xff
        high_byte = self._read_byte_from_current_address_verbose(
            desc='Fetch Base Address high-byte (BAH) @ (00, IAL + 1)'
        )
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address_verbose(
            desc='Fetch DATA @ (BAH, BAL + Y)'
        ), 5, disasm_operand
        if low_byte >> 8 or self._write_buffer:
            self._cycle_log[-1][0] = 'Fetch DATA @ (BAH, BAL + Y) [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                value = self._write_byte_to_current_address_verbose(
                    desc='Write DATA @ (BAH + C, BAL + Y)'
                ), 6, disasm_operand
            else:
                value = self._read_byte_from_current_address_verbose(
                    desc='Fetch DATA @ (BAH + 1, BAL + Y)'
                ), 6, disasm_operand

        return value


    """
    #    
    #    OP CODE IMPLEMENTATIONS
    #    
    """

    ###
    # [ADC] Add Memory to Accumulator with Carry
    # [SBC] Subtract Memory From Accumulator with Borrow
    ###
    def _inst_adc_sbc(self) -> int:
        subtract = self._current_data >> 7
        value, cycles = self._addressing_modes[self._current_data & 0x1F]()
        self._execute_adc_sbc(value, subtract)
        return cycles

    def _inst_adc_sbc_verbose(self) -> tuple[str, int]:
        subtract = self._current_data >> 7
        value, cycles, operand = self._verbose_addressing_modes[self._current_data & 0x1F]()
        self._execute_adc_sbc(value, subtract)
        return f'{"SBC" if subtract else "ADC"} {operand}', cycles

    def _execute_adc_sbc(self, value: int, subtract: bool) -> None:
        if self._get_decimal_mode():
            ##
            ## I hate BCD so much!
            ##
            temp_val = (
                (self._registers[ACC] & 0x0f) +
                (1 - 2 * subtract) * (value & 0x0f) + self._get_carry_flag() - subtract
            )
            if subtract:
                bin_result = self._registers[ACC] + (value^0xff) + self._get_carry_flag()
                self._set_zero_flag(not bin_result & 0xff)
                if temp_val < 0:
                    temp_val = ((temp_val - 0x06) & 0x0f) - 0x10
                result = (self._registers[ACC] & 0xf0) - (value & 0xf0) + temp_val
                if result < 0:
                    result -= 0x60
                self._set_carry_flag(result >= 0)
                value ^= 0xff
                self._set_overflow_flag(bool(
                    (self._registers[ACC]^(bin_result & 0xff)) & (value^(bin_result & 0xff)) & 0x80
                ))
                self._registers[ACC] = result & 0xff
                self._set_negative_flag((bin_result & 0b10000000) >> 7)
            else:
                self._set_zero_flag(
                    not ((self._registers[ACC] + value + self._get_carry_flag()) & 0xff)
                )
                if temp_val >= 0x0a:
                    temp_val = ((temp_val + 0x06) & 0x0f) + 0x10
                result = (self._registers[ACC] & 0xf0) + (value & 0xf0) + temp_val
                if result >= 0xa0:
                    result += 0x60
                self._set_carry_flag(result >= 0x100)

                signed_acc = self._registers[ACC] & 0xf0
                signed_acc = signed_acc - (256 * (signed_acc >> 7))
                signed_val = value & 0xf0
                signed_val = signed_val - (256 * (signed_val >> 7))
                signed_result = signed_acc + signed_val + temp_val
                self._set_negative_flag((signed_result & 0b10000000) >> 7)
                self._set_overflow_flag(signed_result < -128 or signed_result > 127)

                self._registers[ACC] = result & 0xff

        else:
            # Convert to signed numbers
            value ^= (0xff * subtract)
            result = self._registers[ACC] + value + self._get_carry_flag()
            self._set_carry_flag(result >> 8)
            result &= 0xff
            self._set_overflow_flag(bool((self._registers[ACC]^result) & (value^result) & 0x80))
            self._registers[ACC] = result
            self._set_zero_flag(not result)
            self._set_negative_flag((result & 0b10000000) >> 7)

    ###
    # [BIT] Test Bits in Memory with Accumulator
    ###
    def _inst_bit_test(self) -> int:
        value, cycles = self._addressing_modes[self._current_data & 0x1F]()
        self._set_negative_flag(value >> 7)
        self._set_overflow_flag((value & 0b01000000) >> 6)
        self._set_zero_flag(not value & self._registers[ACC])
        return cycles

    def _inst_bit_test_verbose(self) -> tuple[str, int]:
        value, cycles, operand = self._verbose_addressing_modes[self._current_data & 0x1F]()
        self._set_negative_flag(value >> 7)
        self._set_overflow_flag((value & 0b01000000) >> 6)
        self._set_zero_flag(not value & self._registers[ACC])
        return f'BIT {operand}', cycles

    ###
    # [BCC] Branch on Carry Clear
    # [BCS] Branch on Carry Set
    # [BEQ] Branch on Result Zero (Zero Set)
    # [BMI] Branch on Result Minus (Negative Set)
    # [BNE] Branch on Result Not Zero (Zero Clear)
    # [BPL] Branch on Result Plus (Negative Clear)
    # [BVC] Branch on Overflow Clear
    # [BVS] Branch on Overflow Set
    ###
    BRANCH_OP_CODES = ('BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ')
    BRANCH_FLAG_BITS = (7, 6, 0, 1)
    def _inst_branch(self) -> int:
        opcode_int = self._current_data >> 5
        offset = self._read_next_program_byte()
        relative_offset = (offset ^ 0x80) - 0x80 # Convert from unsigned byte to signed byte
        jump_address = (
            ((self._registers[PCH] << 8) | self._registers[PCL]) + relative_offset
        ) & 0xffff
        flag_bit = MOS6502.BRANCH_FLAG_BITS[opcode_int >> 1]
        flag_status = (self._registers[P] >> flag_bit) & 1
        branch_taken = not flag_status ^ (opcode_int & 1)
        if branch_taken:
            pcl = self._registers[PCL]
            self._registers[PCL] = (pcl + offset) & 0xff
            self._read_next_program_byte(advance=False)
            if pcl + relative_offset != self._registers[PCL]: # Page was crossed
                self._registers[PCH] = jump_address >> 8
                self._read_next_program_byte(advance=False)
                return 4
            return 3

        return 2

    def _inst_branch_verbose(self) -> tuple[str, int]:
        opcode_int = self._current_data >> 5
        offset = self._read_next_program_byte_verbose(
            desc='Fetch Branch Offset @ PC + 1 [BRANCH NOT TAKEN]'
        )
        cycles = 2
        relative_offset = (offset ^ 0x80) - 0x80 # Convert from unsigned byte to signed byte
        jump_address = (
            ((self._registers[PCH] << 8) | self._registers[PCL]) + relative_offset
        ) & 0xffff

        flag_bit = MOS6502.BRANCH_FLAG_BITS[opcode_int >> 1]
        flag_status = (self._registers[P] >> flag_bit) & 1
        branch_taken = not flag_status ^ (opcode_int & 1)

        if branch_taken:
            self._cycle_log[-1][0] = 'Fetch Branch Offset @ PC + 1 [BRANCH TAKEN]'
            pcl = self._registers[PCL]
            self._registers[PCL] = (pcl + offset) & 0xff
            self._read_next_program_byte_verbose(
                advance=False,
                desc='Fetch OP CODE @ PC + 2 + Offset w/o carry [DISCARDED]'
            )
            cycles += 1

            if pcl + relative_offset != self._registers[PCL]: # Page was crossed
                self._registers[PCH] = jump_address >> 8
                self._read_next_program_byte_verbose(
                    advance=False,
                    desc='Fetch OP CODE @ PC + 2 + Offset with carry [DISCARDED]'
                )
                cycles += 1

        return f'{MOS6502.BRANCH_OP_CODES[opcode_int]} ${jump_address:04X}', cycles

    ###
    # [BRK] Break Operation
    # [IRQ] Interrupt Request
    # [NMI] Non-maskable Interrupt
    # [RES] Reset Operation
    #
    # "brk_type" argument:
    #     0: BRK
    #     1: IRQ
    #     2: NMI
    #     3: RES
    ###
    BREAK_OP_CODES = (
        ('BRK',   0xFFFE),
        ('IRQ',   0xFFFE),
        ('NMI',   0xFFFA),
        ('RESET', 0xFFFC)
    )
    def _inst_break(self, brk_type: int=0) -> int:
        old_p = self._registers[P]
        self._registers[P] |= 0b00110100
        int_vector = MOS6502.BREAK_OP_CODES[brk_type][1]

        if brk_type:
            self._set_break_flag(not brk_type ^ 3)
            address = ((self._registers[PCH] << 8) | self._registers[PCL]) - 1
            self._registers[PCL] = address & 0xff
            self._registers[PCH] = (address & 0xff00) >> 8
            self._read_next_program_byte(advance=False)
            self._read_next_program_byte()
        else:
            self._set_break_flag(1)
            self._read_next_program_byte()

        self._current_data = self._registers[PCH]
        self._stack_push_current_data()
        self._current_data = self._registers[PCL]
        self._stack_push_current_data()
        self._current_data = old_p
        self._stack_push_current_data()

        self._current_address = int_vector
        adl = self._read_byte_from_current_address()
        self._current_address = int_vector + 1
        adh = self._read_byte_from_current_address()

        self._registers[PCL] = adl
        self._registers[PCH] = adh

        return 7

    def _inst_break_verbose(self, brk_type: int=0) -> tuple[str, int]:
        old_p = self._registers[P]
        self._registers[P] |= 0b00110100
        int_vector = MOS6502.BREAK_OP_CODES[brk_type][1]

        if brk_type:
            self._set_break_flag(not brk_type ^ 3)
            address = ((self._registers[PCH] << 8) | self._registers[PCL]) - 1
            self._registers[PCL] = address & 0xff
            self._registers[PCH] = (address & 0xff00) >> 8
            self._read_next_program_byte_verbose(
                advance=False,
                desc='Hardware Interrupt/Reset initiated'
            )
            self._cycle_log[0][2] = 0 # Set DATA of first cycle to 0x00
            self._read_next_program_byte_verbose(
                desc='Fetch DATA @ PC [DISCARDED]'
            )
        else:
            self._set_break_flag(1)
            self._read_next_program_byte_verbose(
                desc='Fetch DATA @ PC + 1 [DISCARDED]'
            )

        self._current_data = self._registers[PCH]
        self._stack_push_current_data_verbose(
            desc='Write PC high-byte to stack @ S'
        )
        self._current_data = self._registers[PCL]
        self._stack_push_current_data_verbose(
            desc='Write PC low-byte to stack @ S - 1'
        )
        self._current_data = old_p
        self._stack_push_current_data_verbose(
            desc='Write P to stack @ S - 2'
        )

        self._current_address = int_vector
        adl = self._read_byte_from_current_address_verbose(
            desc=f'Fetch Interrup Vector low-byte (ADL) @ ${self._current_address:04X}'
        )
        self._current_address = int_vector + 1
        adh = self._read_byte_from_current_address_verbose(
            desc=f'Fetch Interrup Vector high-byte (ADH) @ ${self._current_address:04X}'
        )

        self._registers[PCL] = adl
        self._registers[PCH] = adh

        return MOS6502.BREAK_OP_CODES[brk_type][0], 7

    ###
    # [CLC] Clear Carry Flag
    # [CLD] Clear Decimal Mode
    # [CLI] Clear Interrupt Disable Bit
    # [CLV] Clear Overflow Flag
    # [SEC] Set Carry Flag
    # [SED] Set Decimal Mode
    # [SEI] Set Interrupt Disable Bit
    ###
    def _inst_clear_set_flag(self) -> int:
        if self._current_data == 0xB8:
            self._set_overflow_flag(0)
        else:
            [
                self._set_carry_flag,
                self._set_irq_disable_flag,
                None,
                self._set_decimal_mode
            ][self._current_data >> 6](
                (self._current_data & 0b00100000) >> 5
            )

        self._read_next_program_byte(advance=False)
        return 2

    def _inst_clear_set_flag_verbose(self) -> tuple[str, int]:
        if self._current_data == 0xB8:
            self._set_overflow_flag(0)
            opcode = 'CLV'
        else:
            reg = ['C', 'I', None, 'D'][self._current_data >> 6]
            set_value = self._current_data & 0b00100000
            opcode = ('SE' if set_value else 'CL') + reg
            {
                'C': self._set_carry_flag,
                'D': self._set_decimal_mode,
                'I': self._set_irq_disable_flag,
            }[reg](set_value >> 5)

        self._read_next_program_byte_verbose(
            advance=False,
            desc='Fetch OP CODE @ PC + 1 [DISCARDED]'
        )
        return opcode, 2

    ###
    # [CMP] Compare Memory and Accumulator
    # [CPX] Compare Memory and Index X
    # [CPY] Compare Memory and Index Y
    ###
    COMPARE_OPCODES = (
        ('CPY', Y),
        ('CMP', ACC),
        ('CPX', X)
    )
    def _inst_compare(self) -> int:
        opcode = MOS6502.COMPARE_OPCODES[
            ((self._current_data & 0b00100000) >> 4) | (self._current_data & 1)
        ][1]

        # Coerce OP Code to be in a nice arrangement for mode detection.
        # A low-byte of 0 is not defined in our data fetch function, so
        # add 2 so that it can be detected as IMMEDIATE addressing mode
        if not self._current_data & 0x0F:
            self._current_data += 2

        value, cycles = self._addressing_modes[self._current_data & 0x1F]()

        # Convert to 2's complement to subtract
        value = (value ^ 0xff) + 1

        result = self._registers[opcode] + value

        self._set_negative_flag((result & 0b10000000) >> 7)
        self._set_zero_flag(not result & 0xff)
        self._set_carry_flag(result >> 8)

        return cycles

    def _inst_compare_verbose(self) -> tuple[str, int]:
        opcode = MOS6502.COMPARE_OPCODES[
            ((self._current_data & 0b00100000) >> 4) | (self._current_data & 1)
        ]

        # Coerce OP Code to be in a nice arrangement for mode detection.
        # A low-byte of 0 is not defined in our data fetch function, so
        # add 2 so that it can be detected as IMMEDIATE addressing mode
        if not self._current_data & 0x0F:
            self._current_data += 2

        value, cycles, operand = self._verbose_addressing_modes[self._current_data & 0x1F]()

        # Convert to 2's complement to subtract
        value = (value ^ 0xff) + 1

        result = self._registers[opcode[1]] + value

        self._set_negative_flag((result & 0b10000000) >> 7)
        self._set_zero_flag(not result & 0xff)
        self._set_carry_flag(result >> 8)

        return f'{opcode[0]} {operand}', cycles

    ###
    # [DEX] Decrement X by 1
    # [DEY] Decrement Y by 1
    # [INX] Increment X by 1
    # [INY] Increment Y by 1
    ###
    def _inst_inc_dec_xy(self) -> int:
        index = X if self._current_data >= 0xCA else Y
        self._registers[index] += 2 * (self._current_data in (0xE8, 0xC8)) - 1
        self._registers[index] &= 0xff
        self._set_zero_flag(not self._registers[index])
        self._set_negative_flag(self._registers[index] >> 7)
        self._read_next_program_byte(advance=False)
        return 2

    def _inst_inc_dec_xy_verbose(self) -> tuple[str, int]:
        index = X if self._current_data >= 0xCA else Y
        inc = self._current_data in (0xE8, 0xC8)
        opcode = ('IN' if inc else 'DE') + [None, 'X', 'Y'][index]

        self._registers[index] += 2 * inc - 1
        self._registers[index] &= 0xff
        self._set_zero_flag(not self._registers[index])
        self._set_negative_flag(self._registers[index] >> 7)
        self._read_next_program_byte_verbose(
            advance=False,
            desc='Fetch OP CODE @ PC + 1 [DISCARDED]'
        )
        return opcode, 2

    ###
    # [JMP] Jump Operation
    ###
    def _inst_jump(self) -> int:
        if self._current_data == 0x4C: # Absolute addressing
            adl = self._read_next_program_byte()
            adh = self._read_next_program_byte()
            self._registers[PCL] = adl
            self._registers[PCH] = adh
            return 3

        # Indirect addressing
        ial = self._read_next_program_byte()
        iah = self._read_next_program_byte()
        self._current_address = (iah << 8) | ial
        adl = self._read_byte_from_current_address()

        # This looks like a bug because of no carry over, but this is how the original 6502
        # was implemented.
        self._current_address = (iah << 8) | ((ial + 1) & 0xff)
        adh = self._read_byte_from_current_address()

        self._registers[PCL] = adl
        self._registers[PCH] = adh

        return 5

    def _inst_jump_verbose(self) -> tuple[str, int]:
        if self._current_data == 0x4C: # Absolute addressing
            adl = self._read_next_program_byte_verbose(
                desc='Fetch Jump Address low-byte (ADL) @ PC + 1'
            )
            adh = self._read_next_program_byte_verbose(
                desc='Fetch Jump Address high-byte (ADH) @ PC + 2'
            )
            self._registers[PCL] = adl
            self._registers[PCH] = adh
            return f'JMP ${(adh << 8) | adl:04X}', 3

        # Indirect addressing
        ial = self._read_next_program_byte_verbose(
            desc='Fetch Indirect Address low-byte (IAL) @ PC + 1'
        )
        iah = self._read_next_program_byte_verbose(
            desc='Fetch Indirect Address high-byte (IAH) @ PC + 2'
        )
        self._current_address = (iah << 8) | ial
        adl = self._read_byte_from_current_address_verbose(
            desc='Fetch Jump Address low-byte (ADL) @ (IAH, IAL)'
        )

        # This looks like a bug because of no carry over, but this is how the original 6502
        # was implemented.
        self._current_address = (iah << 8) | ((ial + 1) & 0xff)
        adh = self._read_byte_from_current_address_verbose(
            desc='Fetch Jump Address high-byte (ADH) @ (IAH, IAL + 1)'
        )

        self._registers[PCL] = adl
        self._registers[PCH] = adh
        return f'JMP (${(iah << 8) | ial:04X})', 5

    ###
    # [JSR] Jump to Subroutine
    ###
    def _inst_jump_to_subroutine(self) -> int:
        adl = self._read_next_program_byte()
        self._current_address = 0x0100 | self._registers[S]
        self._read_byte_from_current_address()
        self._current_data = self._registers[PCH]
        self._stack_push_current_data()
        self._current_data = self._registers[PCL]
        self._stack_push_current_data()

        adh = self._read_next_program_byte()
        self._registers[PCL] = adl
        self._registers[PCH] = adh
        return 6

    def _inst_jump_to_subroutine_verbose(self) -> tuple[str, int]:

        adl = self._read_next_program_byte_verbose(
            desc='Fetch Subroutine Address low-byte (ADL) @ PC + 1'
        )

        self._current_address = 0x0100 | self._registers[S]
        self._read_byte_from_current_address_verbose(
            desc='Fetch DATA from stack @ S [DISCARDED]'
        )
        self._current_data = self._registers[PCH]
        self._stack_push_current_data_verbose(
            desc='Write PC high-byte to stack @ S'
        )
        self._current_data = self._registers[PCL]
        self._stack_push_current_data_verbose(
            desc='Write PC low-byte to stack @ S - 1'
        )

        adh = self._read_next_program_byte_verbose(
            desc='Fetch Subroutine Address high-byte (ADH) @ PC + 2'
        )
        self._registers[PCL] = adl
        self._registers[PCH] = adh

        return f'JSR ${(adh << 8) | adl:04X}', 6

    ###
    # [LDA] Load Accumulator with Memory
    # [LDX] Load Index X with Memory
    # [LDY] Load Index Y with Memory
    ###
    LOAD_OPCODES = (
        ('LDY', Y),
        ('LDA', ACC),
        ('LDX', X)
    )
    def _inst_load_from_memory(self) -> int:
        opcode = MOS6502.LOAD_OPCODES[self._current_data & 3][1]
        # Coerce OP Code to be in a nice arrangement for mode detection.
        # A low-byte of 0 is not defined in our data fetch function, so
        # add 2 so that it can be detected as IMMEDIATE addressing mode
        if not self._current_data & 0x0F:
            self._current_data += 2

        if self._current_data == 0xB6: # Handle special case of "LDX zp,y"
            value, cycles = self._zp_y_mode_fetch_write_data()
        elif self._current_data == 0xBE: # Handle special case of "LDX a,y"
            value, cycles = self._abs_y_mode_fetch_write_data()
        else:
            value, cycles = self._addressing_modes[self._current_data & 0x1F]()

        self._registers[opcode] = value
        self._set_negative_flag(value >> 7)
        self._set_zero_flag(not value)

        return cycles

    def _inst_load_from_memory_verbose(self) -> tuple[str, int]:
        opcode = MOS6502.LOAD_OPCODES[self._current_data & 3]

        # Coerce OP Code to be in a nice arrangement for mode detection.
        # A low-byte of 0 is not defined in our data fetch function, so
        # add 2 so that it can be detected as IMMEDIATE addressing mode
        if not self._current_data & 0x0F:
            self._current_data += 2

        if self._current_data == 0xB6: # Handle special case of "LDX zp,y"
            value, cycles, operand = self._zp_y_mode_fetch_write_data_verbose()
        elif self._current_data == 0xBE: # Handle special case of "LDX a,y"
            value, cycles, operand = self._abs_y_mode_fetch_write_data_verbose()
        else:
            value, cycles, operand = self._verbose_addressing_modes[self._current_data & 0x1F]()

        self._registers[opcode[1]] = value
        self._set_negative_flag(value >> 7)
        self._set_zero_flag(not value)

        return f'{opcode[0]} {operand}', cycles

    ###
    # [AND] "AND" Memory with Accumulator
    # [EOR] "XOR" Memory with Accumulator
    # [ORA] "OR" Memory with Accumulator
    ###
    def _inst_logic(self) -> int:
        opcode_int = self._current_data >> 5
        value, cycles = self._addressing_modes[self._current_data & 0x1F]()
        acc = self._registers[ACC]
        result = (acc|value) if not opcode_int else (acc&value) if opcode_int == 1 else (acc^value)
        self._registers[ACC] = result
        self._set_negative_flag(result >> 7)
        self._set_zero_flag(not result)
        return cycles

    def _inst_logic_verbose(self) -> tuple[str, int]:
        opcode_int = self._current_data >> 5
        value, cycles, operand = self._verbose_addressing_modes[self._current_data & 0x1F]()

        acc = self._registers[ACC]
        result = (acc|value) if not opcode_int else (acc&value) if opcode_int == 1 else (acc^value)

        self._registers[ACC] = result
        self._set_negative_flag(result >> 7)
        self._set_zero_flag(not result)

        return f'{"ORA" if not opcode_int else "AND" if opcode_int==1 else "EOR"} {operand}', cycles

    ###
    # [NOP] No Operation
    ###
    def _inst_nop(self) -> int:
        self._read_next_program_byte(advance=False)
        return 2

    def _inst_nop_verbose(self) -> tuple[str, int]:
        self._read_next_program_byte_verbose(
            advance=False,
            desc='Fetch OP CODE @ PC + 1 [DISCARDED]'
        )
        return 'NOP', 2

    ###
    # [PHA] Push Accumulator on Stack
    # [PHP] Push Status Register on Stack
    # [PLA] Pull Accumulator from Stack
    # [PLP] Pull Status Register from Stack
    ###
    _PUSH_PULL_OP_CODES = (
        (P, 0, 'PHP'),
        (P, 1, 'PLP'),
        (ACC, 0, 'PHA'),
        (ACC, 1, 'PLA'),
    )
    def _inst_push_pull_stack(self) -> int:
        reg, read, _ = MOS6502._PUSH_PULL_OP_CODES[self._current_data >> 5]
        self._read_next_program_byte(advance=False)

        if read:
            # Remember current state of Bits 4 and 5 in case of PLP
            bits45 = self._registers[P] & 0b00110000
            self._current_address = 0x0100 | self._registers[S]
            self._read_byte_from_current_address()
            self._registers[reg] = self._stack_pull()

            if not reg: # Accumulator pulled
                self._set_negative_flag(self._registers[ACC] >> 7)
                self._set_zero_flag(not self._registers[ACC])

            else: # Processor Status Register pulled
                # Restore P, but leave bits 4 and 5 unchanged
                self._registers[P] &= 0b11001111
                self._registers[P] |= bits45
        else:
            self._current_data = self._registers[reg]
            self._stack_push_current_data()

        return 3 + read

    def _inst_push_pull_stack_verbose(self) -> tuple[str, int]:
        reg, read, opcode_str = MOS6502._PUSH_PULL_OP_CODES[self._current_data >> 5]
        self._read_next_program_byte_verbose(
            advance=False,
            desc='Fetch OP CODE @ PC + 1 [DISCARDED]'
        )

        if read:
            # Remember current state of Bits 4 and 5 in case of PLP
            bits45 = self._registers[P] & 0b00110000
            self._current_address = 0x0100 | self._registers[S]
            self._read_byte_from_current_address_verbose(
                desc='Fetch DATA from stack @ S [DISCARDED]'
            )
            self._registers[reg] = self._stack_pull_verbose(
                desc=f'Fetch {reg} from stack @ S + 1'
            )

            if not reg: # Accumulator pulled
                self._set_negative_flag(self._registers[ACC] >> 7)
                self._set_zero_flag(not self._registers[ACC])

            else: # Processor Status Register pulled
                # Restore P, but leave bits 4 and 5 unchanged
                self._registers[P] &= 0b11001111
                self._registers[P] |= bits45
        else:
            self._current_data = self._registers[reg]
            self._stack_push_current_data_verbose(
                desc=f'Write {opcode_str[-1] if reg else "ACC"} to stack @ S'
            )

        return opcode_str, 3 + read

    ###
    # [RTI] Return from Interrupt
    # [RTS] Return from Subroutine
    ###
    _RETURN_OP_CODES = (None, None, 'RTI', 'RTS')
    def _inst_return(self) -> int:
        opcode_int = self._current_data >> 5
        self._read_next_program_byte(advance=False)
        self._current_address = 0x0100 | self._registers[S]
        self._read_byte_from_current_address()

        if opcode_int == 2: # Return from Interrupt
            bits45 = self._registers[P] & 0b00110000
            self._registers[P] = self._stack_pull() & 0b11001111 # Ignore BRK flag and Bit 5
            self._registers[P] |= bits45
            self._registers[PCL] = self._stack_pull()
            self._registers[PCH] = self._stack_pull()
            return 6

        # Return from Subroutine
        self._registers[PCL] = self._stack_pull()
        self._registers[PCH] = self._stack_pull()

        self._read_next_program_byte()
        return 6

    def _inst_return_verbose(self) -> tuple[str, int]:
        opcode_int = self._current_data >> 5
        opcode_str = MOS6502._RETURN_OP_CODES[opcode_int]

        self._read_next_program_byte_verbose(
            advance=False,
            desc='Fetch DATA @ PC + 1 [DISCARDED]'
        )
        self._current_address = 0x0100 | self._registers[S]
        self._read_byte_from_current_address_verbose(
            desc='Fetch DATA from stack @ S [DISCARDED]'
        )

        if opcode_int == 2: # Return from Interrupt
            bits45 = self._registers[P] & 0b00110000
            self._registers[P] = self._stack_pull_verbose(
                desc='Fetch P from stack @ S + 1'
            ) & 0b11001111 # Ignore BRK flag and Bit 5
            self._registers[P] |= bits45
            self._registers[PCL] = self._stack_pull_verbose(
                desc='Fetch PCL from stack @ S + 2'
            )
            self._registers[PCH] = self._stack_pull_verbose(
                desc='Fetch PCH from stack @ S + 3'
            )
            return opcode_str, 6

        # Return from Subroutine
        self._registers[PCL] = self._stack_pull_verbose(
            desc='Fetch PC low-byte from stack (PCL) @ S + 1'
        )
        self._registers[PCH] = self._stack_pull_verbose(
            desc='Fetch PC high-byte from stack (PCH) @ S + 2'
        )
        self._read_next_program_byte_verbose(
            desc='Fetch DATA @ (PCH, PCL) [DISCARDED]'
        )
        return opcode_str, 6

    ###
    # [ASL] Arithmetic Shift Left by 1 Bit
    # [DEC] Decrement Memory by 1
    # [INC] Increment Memory by 1
    # [LSR] Logic Shift Right by 1 Bit
    # [ROL] Rotate 1 Bit Left
    # [ROR] Rotate 1 Bit Right
    ###
    _READ_MOD_WRITE_OPS = ('ASL', 'ROL', 'LSR', 'ROR', None, None, 'DEC', 'INC')
    def _inst_read_mod_write(self) -> int:
        opcode_int = self._current_data >> 5
        mode = self._current_data & 0x1f

        # Retrieve value first
        value, cycles = self._addressing_modes[mode](True)

        # Change value and flags
        if opcode_int == 0: # ASL
            self._set_carry_flag(value >> 7)
            value = (value << 1) & 0xff
        elif opcode_int == 1: # ROL
            value = (value << 1) | self._get_carry_flag()
            self._set_carry_flag(value >> 8)
            value &= 0xff
        elif opcode_int == 2: # LSR
            self._set_carry_flag(value & 1)
            value >>= 1
        elif opcode_int == 3: # ROR
            temp_carry = value & 1
            value = (value >> 1) | (self._get_carry_flag() << 7)
            self._set_carry_flag(temp_carry)
        elif opcode_int == 6: # DEC
            value -= 1
            value &= 0xff
        else: # INC
            value += 1
            value &= 0xff

        self._set_zero_flag(not value)
        self._set_negative_flag(value >> 7)

        # Execute final steps for accumulator mode of address
        if mode == 0x0A:
            self._registers[ACC] = value
            self._read_next_program_byte(advance=False)
            return 2

        # Execute final steps for other modes
        self._write_byte_to_current_address()
        self._current_data = value
        self._write_byte_to_current_address()

        return cycles

    def _inst_read_mod_write_verbose(self) -> tuple[str, int]:
        opcode_int = self._current_data >> 5
        opcode_str = MOS6502._READ_MOD_WRITE_OPS[opcode_int]
        mode = self._current_data & 0x1f

        # Retrieve value first
        value, cycles, operand = self._verbose_addressing_modes[mode](True)

        # Change value and flags
        if opcode_int == 0: # ASL
            self._set_carry_flag(value >> 7)
            value = (value << 1) & 0xff
        elif opcode_int == 1: # ROL
            value = (value << 1) | self._get_carry_flag()
            self._set_carry_flag(value >> 8)
            value &= 0xff
        elif opcode_int == 2: # LSR
            self._set_carry_flag(value & 1)
            value >>= 1
        elif opcode_int == 3: # ROR
            temp_carry = value & 1
            value = (value >> 1) | (self._get_carry_flag() << 7)
            self._set_carry_flag(temp_carry)
        elif opcode_int == 6: # DEC
            value -= 1
            value &= 0xff
        else: # INC
            value += 1
            value &= 0xff

        self._set_zero_flag(not value)
        self._set_negative_flag(value >> 7)

        # Execute final steps for accumulator mode of address
        if mode == 0x0A:
            self._registers[ACC] = value
            self._read_next_program_byte_verbose(
                advance=False,
                desc='Fetch OP CODE @ PC + 1 [DISCARDED]'
            )
            return opcode_str, 2

        # Execute final steps for other modes
        micro_desc_msg = self._cycle_log[-1][0][5:]
        self._write_byte_to_current_address_verbose(
            desc=f'Write{micro_desc_msg}'
        )
        self._current_data = value
        self._write_byte_to_current_address_verbose(
            desc=f'Write Modified{micro_desc_msg}'
        )

        return f'{opcode_str} {operand}', cycles

    ###
    # [STA] Store Accumulator in Memory
    # [STX] Store Index X in Memory
    # [STY] Store Index Y in Memory
    ###
    STORE_OPCODES = (
        ('STY', Y),
        ('STA', ACC),
        ('STX', X),
    )
    def _inst_store_in_memory(self) -> int:
        self._write_buffer.append(self._registers[MOS6502.STORE_OPCODES[self._current_data & 3][1]])
        if self._current_data == 0x96: # Handle special case of "STX zp,y"
            _, cycles = self._zp_y_mode_fetch_write_data()
        else:
            _, cycles = self._addressing_modes[self._current_data & 0x1F]()
        return cycles

    def _inst_store_in_memory_verbose(self) -> tuple[str, int]:
        opcode = MOS6502.STORE_OPCODES[self._current_data & 3]
        self._write_buffer.append(self._registers[opcode[1]])
        if self._current_data == 0x96: # Handle special case of "STX zp,y"
            _, cycles, operand = self._zp_y_mode_fetch_write_data_verbose()
        else:
            _, cycles, operand = self._verbose_addressing_modes[self._current_data & 0x1F]()
        return f'{opcode[0]} {operand}', cycles

    ###
    # [TAX] Transfer Accumulator to Index X
    # [TAY] Transfer Accumulator to Index Y
    # [TSX] Transfer Stack Pointer to Index X
    # [TXA] Transfer Index X to Accumulator
    # [TXS] Transfer Index X to Stack Pointer
    # [TYA] Transfer Index Y to Accumulator
    ###
    TRANSFER_OPCODES = (
        ('TXA', X, ACC),
        None,
        ('TXS', X, S),
        ('TYA', Y, ACC),
        ('TAX', ACC, X),
        ('TAY', ACC, Y),
        ('TSX', S, X),
    )
    def _inst_transfer(self) -> int:
        opcode = MOS6502.TRANSFER_OPCODES[
            ((self._current_data & 0b00111000) >> 3) - ((self._current_data & 0b00000010) >> 1)
        ]
        self._registers[opcode[2]] = self._registers[opcode[1]]
        if self._current_data != 0x9A:
            self._set_negative_flag(self._registers[opcode[1]] >> 7)
            self._set_zero_flag(not self._registers[opcode[1]])
        self._read_next_program_byte(advance=False)

        return 2

    def _inst_transfer_verbose(self) -> tuple[str, int]:
        opcode = MOS6502.TRANSFER_OPCODES[
            ((self._current_data & 0b00111000) >> 3) - ((self._current_data & 0b00000010) >> 1)
        ]
        self._registers[opcode[2]] = self._registers[opcode[1]]
        if self._current_data != 0x9A:
            self._set_negative_flag(self._registers[opcode[1]] >> 7)
            self._set_zero_flag(not self._registers[opcode[1]])
        self._read_next_program_byte_verbose(
            advance=False,
            desc='Fetch OP CODE @ PC + 1 [DISCARDED]'
        )
        return opcode[0], 2
