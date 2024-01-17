"""
Simulator definitions and functions for the main 6502 micro processor
"""
from py6502sim import Component

# TODO:
#   * [IMPLEMENTATION] Implement Decimal Mode in ADC and SBC
#   * [OPTIMIZATION] Move constants to separate file/class ?? Do I need to? Yes, because I don't
#                    want users to be exposed to too many weird variables on importing a class
#   * [OPTIMIZATION] Convert registers from dict -> array
#   * [OPTIMIZATION] Put data fetch/write addressing modes in array instead of if/else switch case


class MOS6502:
    """
    Class definition for the main MOS 6502 processor

    Based on the 1976 revision of the MCS6502 processor
    """
    def __init__(self, memory: Component) -> None:
        self._memory = memory
        self._current_data = 0
        self._current_address = 0
        self._write_buffer = []
        self._disasm_tokens = []

        # Cycle log will contain a list of tuples in the form:
        # (
        #     micro-instruction description,
        #     address,
        #     data,
        #     read / write,
        #     disassembled code as a string,
        #     registers dictionary (LAST MICRO-INSTRUCTIONS ONLY)
        # )
        self._cycle_log: list[list] = []

        self._registers = {
            'ACC': 0,   # Accumulator
            'X': 0,     # Index Register X
            'Y': 0,     # Index Register Y
            'PCL': 0,   # Program Counter Low-byte   
            'PCH': 0,   # Program Counter High-byte

            'S': 0,
            # Stack Pointer S is always "zero-paged". The pointer is always technically a 9-bit
            # number where bit 9 is always "1" and the bits 1 - 8 provide the 8-bit address in the
            # stack. I.e. S always points to addresses in the range 0x0100 ~ 0x01FF. Our
            # implementation will treat S as 8-bit, and assume it is always offset to 0x01XX.

            'P': 0,
            # Processor Status Register P is an 8-bit register that contains various flags:
            # Bit 0 - Carry (C)
            # Bit 1 - Zero (Z)
            # Bit 2 - IRQ Disable (I)
            # Bit 3 - Decimal Mode (D)
            # Bit 4 - BRK Command (B)
            # Bit 5 -
            # Bit 6 - Overflow (V)
            # Bit 7 - Negative (N)
        }

        # This is easier to type and organize for a human
        # Just temporary and not meant to be an instance/class variable
        instructions = {
            # [ADC] Add Memory to Accumulator with Carry
            # [SBC] Subtract Memory From Accumulator with Borrow
            (0x69, 0x6D, 0x65, 0x61, 0x71, 0x75, 0x7D, 0x79,
             0xE9, 0xED, 0xE5, 0xE1, 0xF1, 0xF5, 0xFD, 0xF9): self._inst_adc_sbc,

            # [AND] "AND" Memory with Accumulator
            # [EOR] "XOR" Memory with Accumulator
            # [ORA] "OR" Memory with Accumulator
            (0x29, 0x2D, 0x25, 0x21, 0x31, 0x35, 0x3D, 0x39,
             0x49, 0x4D, 0x45, 0x41, 0x51, 0x55, 0x5D, 0x59,
             0x09, 0x0D, 0x05, 0x01, 0x11, 0x15, 0x1D, 0x19,): self._inst_logic,

            # [ASL] Arithmetic Shift Left by 1 Bit
            # [DEC] Decrement Memory by 1
            # [INC] Increment Memory by 1
            # [LSR] Logic Shift Right by 1 Bit
            # [ROL] Rotate 1 Bit Left
            # [ROR] Rotate 1 Bit Right
            (0x0E, 0x06, 0x0A, 0x16, 0x1E,
             0xCE, 0xC6,       0xD6, 0xDE,
             0xEE, 0xE6,       0xF6, 0xFE,
             0x4E, 0x46, 0x4A, 0x56, 0x5E,
             0x2E, 0x26, 0x2A, 0x36, 0x3E,
             0x6E, 0x66, 0x6A, 0x76, 0x7E): self._inst_read_mod_write,

            # [BIT] Test Bits in Memory with Accumulator
            (0x2C, 0x24): self._inst_bit_test,

            # [BCC] Branch on Carry Clear
            # [BCS] Branch on Carry Set
            # [BEQ] Branch on Result Zero (Zero Set)
            # [BMI] Branch on Result Minus (Negative Set)
            # [BNE] Branch on Result Not Zero (Zero Clear)
            # [BPL] Branch on Result Plus (Negative Clear)
            # [BVC] Branch on Overflow Clear
            # [BVS] Branch on Overflow Set
            (0x90, 0xB0, 0xF0, 0x30, 0xD0, 0x10, 0x50, 0x70): self._inst_branch,

            # [BRK] Break Operation
            (0x00,): self._inst_break,

            # [CLC] Clear Carry Flag
            # [CLD] Clear Decimal Mode
            # [CLI] Clear Interrupt Disable Bit
            # [CLV] Clear Overflow Flag
            # [SEC] Set Carry Flag
            # [SED] Set Decimal Mode
            # [SEI] Set Interrupt Disable Bit
            (0x18, 0xD8, 0x58, 0xB8, 0x38, 0xF8, 0x78): self._inst_clear_set_flag,

            # [CMP] Compare Memory and Accumulator
            # [CPX] Compare Memory and Index X
            # [CPY] Compare Memory and Index Y
            (0xC9, 0xCD, 0xC5, 0xC1, 0xD1, 0xD5, 0xDD, 0xD9,
             0xE0, 0xEC, 0xE4,
             0xC0, 0xCC, 0xC4,                              ): self._inst_compare,

            # [DEX] Decrement X by 1
            # [DEY] Decrement Y by 1
            # [INX] Increment X by 1
            # [INY] Increment Y by 1
            (0xCA, 0x88, 0xE8, 0xC8): self._inst_inc_dec_xy,

            # [JMP] Jump Operation
            (0x4C, 0x6C): self._inst_jump,

            # [JSR] Jump to Subroutine
            (0x20,): self._inst_jump_to_subroutine,

            # [LDA] Load Accumulator with Memory
            # [LDX] Load Index X with Memory
            # [LDY] Load Index Y with Memory
            (0xA9, 0xAD, 0xA5, 0xA1, 0xB1, 0xB5, 0xBD, 0xB9,
             0xA2, 0xAE, 0xA6, 0xBE, 0xB6,
             0xA0, 0xAC, 0xA4, 0xB4, 0xBC                   ): self._inst_load_from_memory,

            # [NOP] No Operation
            (0xEA,): self._inst_nop,

            # [PHA] Push Accumulator on Stack
            # [PHP] Push Status Register on Stack
            # [PLA] Pull Accumulator from Stack
            # [PLP] Pull Status Register from Stack
            (0x48, 0x08, 0x68, 0x28): self._inst_push_pull_stack,

            # [RTI] Return from Interrupt
            # [RTS] Return from Subroutine
            (0x40, 0x60): self._inst_return,

            # [STA] Store Accumulator in Memory
            # [STX] Store Index X in Memory
            # [STY] Store Index Y in Memory
            (0x8D, 0x85, 0x81, 0x91, 0x95, 0x9D, 0x99,
             0x8E, 0x86, 0x96,
             0x8C, 0x84, 0x94                         ): self._inst_store_in_memory,

            # [TAX] Transfer Accumulator to Index X
            # [TAY] Transfer Accumulator to Index Y
            # [TSX] Transfer Stack Pointer to Index X
            # [TXA] Transfer Index X to Accumulator
            # [TXS] Transfer Index X to Stack Pointer
            # [TYA] Transfer Index Y to Accumulator
            (0xAA, 0xA8, 0xBA, 0x8A, 0x9A, 0x98): self._inst_transfer,
        }

        # This is quicker to access through code for a computer
        self._instructions = [None] * 256
        instruction_gen = ((code, op) for hex_list, op in instructions.items() for code in hex_list)
        for code, op in instruction_gen:
            self._instructions[code] = op


    """
    #    
    #    PUBLIC FACING CONTROL FUNCTIONS
    #    
    """
    def reset(self) -> None:
        """
        Run the processor through the reset sequence.
        """
        self._cycle_log = []
        self._write_buffer = []
        self._inst_break(brk_type=3)

    def step(self, skip_micro: bool=False) -> list:
        """
        Step through clock cycles.

        Arguments:
            skip_micro (bool):
                Whether to skip micro-instructions in output (Default: False)

                If True, clock cycles will automatically proceed until the instruction has finished
                execution. Otherwise, clock cycles will only step 1 clock cycle each time the
                function is called, whether the instruction has finished execution or not.

        Returns:
            A list containing the following
                - Micro-instruction description
                - Address bus value
                - Data bus value
                - Read / Write
                - Disassembled code as a string
                - Registers dictionary (Last micro-instructions only)
        """
        # If no instruction output exists, obtain and execute the next instruction
        if not self._cycle_log:
            self._instructions[self._read_next_program_byte('Fetch OP CODE @ PC: ')]()

            # Ensure that all logs contain the Disassembled Code and append Status Register
            # to the last cycle log.
            disasm_string = self._get_disasm_str()
            for log in self._cycle_log:
                log.append(disasm_string)

            # Append final registers to last micro-instruction log
            self._cycle_log[-1].append(self._registers.copy())

        if skip_micro:
            result = self._cycle_log.pop()
            self._cycle_log = []
        else:
            result = self._cycle_log.pop(0)

        return result


    """
    #    
    #    FLAG GET AND SET FUNCTIONS
    #    
    """
    def _get_carry_flag(self) -> int:
        return self._registers['P'] & 1

    def _get_zero_flag(self) -> int:
        return (self._registers['P'] >> 1) & 1

    def _get_irq_disable_flag(self) -> int:
        return (self._registers['P'] >> 2) & 1

    def _get_decimal_mode(self) -> int:
        return (self._registers['P'] >> 3) & 1

    def _get_break_flag(self) -> int:
        return (self._registers['P'] >> 4) & 1

    def _get_overflow_flag(self) -> int:
        return (self._registers['P'] >> 6) & 1

    def _get_negative_flag(self) -> int:
        return (self._registers['P'] >> 7) & 1

    def _set_carry_flag(self, value: bool):
        if value:
            self._registers['P'] |= 0b1
        else:
            self._registers['P'] &= 0b11111110

    def _set_zero_flag(self, value: bool):
        if value:
            self._registers['P'] |= 0b10
        else:
            self._registers['P'] &= 0b11111101

    def _set_irq_disable_flag(self, value: bool):
        if value:
            self._registers['P'] |= 0b100
        else:
            self._registers['P'] &= 0b11111011

    def _set_decimal_mode(self, value: bool):
        if value:
            self._registers['P'] |= 0b1000
        else:
            self._registers['P'] &= 0b11110111

    def _set_break_flag(self, value: bool):
        if value:
            self._registers['P'] |= 0b10000
        else:
            self._registers['P'] &= 0b11101111

    def _set_overflow_flag(self, value: bool):
        if value:
            self._registers['P'] |= 0b1000000
        else:
            self._registers['P'] &= 0b10111111

    def _set_negative_flag(self, value: bool):
        if value:
            self._registers['P'] |= 0b10000000
        else:
            self._registers['P'] &= 0b01111111



    """
    #    
    #    CYCLE MANAGEMENT FUNCTIONS
    #    
    """
    def _add_disasm_token(self, token_str: str) -> None:
        self._disasm_tokens.append(token_str)

    def _set_disasm_token(self, token_str: str) -> None:
        self._disasm_tokens = [token_str]

    def _get_disasm_str(self):
        return ' '.join(self._disasm_tokens)

    def _append_to_first_micro_desc(self, micro_desc_add: str) -> None:
        self._cycle_log[0][0] += micro_desc_add

    def _read_byte_from_current_address(self, micro_desc: str) -> int:
        self._current_data = self._memory.execute(self._current_address, self._current_data, 1)
        self._cycle_log.append([
            micro_desc,
            self._current_address,
            self._current_data,
            'READ',
        ])
        return self._current_data

    def _write_byte_to_current_address(self, micro_desc: str) -> int:
        self._current_data = self._memory.execute(self._current_address, self._current_data, 0)
        self._cycle_log.append([
            micro_desc,
            self._current_address,
            self._current_data,
            'WRITE',
        ])
        return self._current_data

    def _read_next_program_byte(self, micro_desc: str, advance: bool=True) -> int:
        # Advance is set false with Single Byte Instructions running for 2 clock cycles

        self._current_address = (self._registers['PCH'] << 8) | self._registers['PCL']
        address = self._current_address + advance
        self._registers['PCL'] = address & 0xff
        self._registers['PCH'] = (address & 0xff00) >> 8
        return self._read_byte_from_current_address(micro_desc)


    """
    #    
    #    DATA FETCH/WRITE FUNCTIONS FOR VARIOUS ADDRESSING MODE 
    #    
    """
    _IMM_ABSY = (0x02, 0x09)
    _ABS_ABSX = (0x0C, 0x0D, 0x0E)
    _ZP_ZPX   = (0x04, 0x05, 0x06)
    def _fetch_write_data(self, no_skip: bool=False) -> int:
        mode_high = self._current_data & 0x10
        mode_low = self._current_data & 0x0F

        if mode_low in MOS6502._IMM_ABSY:
            return (
                self._abs_y_mode_fetch_write_data(no_skip) if mode_high # Absolute, Y
                else self._immediate_mode_fetch_write_data()            # Immediate
            )

        if mode_low in MOS6502._ABS_ABSX:
            return (
                self._abs_x_mode_fetch_write_data(no_skip) if mode_high # Absolute, X
                else self._absolute_mode_fetch_write_data()             # Absolute
            )

        if mode_low in MOS6502._ZP_ZPX:
            return (
                self._zp_x_mode_fetch_write_data() if mode_high         # Zero Page, X
                else self._zero_page_mode_fetch_write_data()            # Zero Page
            )

        if mode_low == 0x0A:
            return self._accumulator_mode_fetch_write_data()           # Accumulator

        if mode_low == 0x01:
            return (
                self._ind_y_mode_fetch_write_data() if mode_high        # (Indirect), Y
                else self._ind_x_mode_fetch_write_data()                # (Indirect, X)
            )

        return None

    def _immediate_mode_fetch_write_data(self) -> int:
        self._append_to_first_micro_desc('#')
        value = self._read_next_program_byte('Fetch DATA @ PC + 1')
        self._add_disasm_token(f'#${value:02X}')
        return value

    def _absolute_mode_fetch_write_data(self) -> int:
        self._append_to_first_micro_desc('a')
        low_byte = self._read_next_program_byte(
            'Fetch Effective Address low-byte (ADL) @ PC + 1'
        )
        high_byte = self._read_next_program_byte(
            'Fetch Effective Address high-byte (ADH) @ PC + 2'
        )
        self._current_address = (high_byte << 8) | low_byte
        self._add_disasm_token(f'${self._current_address:04X}')
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address('Write DATA @ (ADH, ADL)')

        return self._read_byte_from_current_address('Fetch DATA @ (ADH, ADL)')

    def _zero_page_mode_fetch_write_data(self) -> int:
        self._append_to_first_micro_desc('zp')
        low_byte = self._read_next_program_byte(
            'Fetch Zero-Page Effective Address (ADL) @ PC + 1'
        )
        self._current_address = low_byte
        self._add_disasm_token(f'${self._current_address:02X}')
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address('Write DATA @ (00, ADL)')

        return self._read_byte_from_current_address('Fetch DATA @ (00, ADL)')

    def _accumulator_mode_fetch_write_data(self) -> int:
        self._append_to_first_micro_desc('ACC')
        self._add_disasm_token('ACC')
        return self._registers['ACC']

    def _zp_x_mode_fetch_write_data(self) -> int:
        self._append_to_first_micro_desc('zp,x')
        self._current_address = self._read_next_program_byte(
            'Fetch Zero-Page Base Address (BAL) @ PC + 1'
        )
        self._add_disasm_token(f'${self._current_address:02X},X')
        self._read_byte_from_current_address('Fetch DATA @ (00, BAL) [DISCARDED]')
        self._current_address = (self._current_address + self._registers['X']) & 0xff
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address('Write DATA @ (00, BAL + X)')

        return self._read_byte_from_current_address(
            'Fetch DATA @ (00, BAL + X)'
        )

    def _zp_y_mode_fetch_write_data(self) -> int:
        self._append_to_first_micro_desc('zp,y')
        self._current_address = self._read_next_program_byte(
            'Fetch Zero-Page Base Address (BAL) @ PC + 1'
        )
        self._add_disasm_token(f'${self._current_address:02X},Y')
        self._read_byte_from_current_address('Fetch DATA @ (00, BAL) [DISCARDED]')
        self._current_address = (self._current_address + self._registers['Y']) & 0xff
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address('Write DATA @ (00, BAL + Y)')

        return self._read_byte_from_current_address(
            'Fetch DATA @ (00, BAL + Y)'
        )

    def _abs_x_mode_fetch_write_data(self, no_skip: bool=False) -> int:
        self._append_to_first_micro_desc('a,x')
        low_byte = self._read_next_program_byte(
            'Fetch Base Address low-byte (BAL) @ PC + 1'
        ) + self._registers['X']
        high_byte = self._read_next_program_byte(
            'Fetch Base Address high-byte (BAH) @ PC + 2'
        )
        self._add_disasm_token(f'${high_byte:02X}{low_byte-self._registers['X']:02X},X')
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address(
            'Fetch DATA @ (BAH, BAL + X)'
        )
        if no_skip or low_byte >> 8 or self._write_buffer:
            self._cycle_log[-1][0] += ' [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff

            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                value = self._write_byte_to_current_address('Write DATA @ (BAH + C, BAL + X)')
            else:
                value = self._read_byte_from_current_address(
                    f'Fetch DATA @ (BAH + {"C" if no_skip else "1"}, BAL + X)'
                )

        return value

    def _abs_y_mode_fetch_write_data(self, no_skip: bool=False) -> int:
        self._append_to_first_micro_desc('a,y')
        low_byte = self._read_next_program_byte(
            'Fetch Base Address low-byte (BAL) @ PC + 1'
        ) + self._registers['X']
        high_byte = self._read_next_program_byte(
            'Fetch Base Address high-byte (BAH) @ PC + 2'
        )
        self._add_disasm_token(f'${high_byte:02X}{low_byte-self._registers['Y']:02X},Y')
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address(
            'Fetch DATA @ (BAH, BAL + Y)'
        )
        if no_skip or low_byte >> 8 or self._write_buffer:
            self._cycle_log[-1][0] += ' [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff

            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                value = self._write_byte_to_current_address('Write DATA @ (BAH + C, BAL + Y)')
            else:
                value = self._read_byte_from_current_address(
                    f'Fetch DATA @ (BAH + {"C" if no_skip else "1"}, BAL + Y)'
                )

        return value

    def _ind_x_mode_fetch_write_data(self) -> int:
        self._append_to_first_micro_desc('(zp,x)')
        self._current_address = self._read_next_program_byte(
            'Fetch Zero-Page Base Address (BAL) @ PC + 1'
        )
        self._add_disasm_token(f'(${self._current_address:02X},X)')
        self._read_byte_from_current_address('Fetch DATA @ (00, BAL) [DISCARDED]')
        self._current_address = (self._current_address + self._registers['X']) & 0xff
        low_byte = self._read_byte_from_current_address(
            'Fetch Effective Address low-byte (ADL) @ (00, BAL + X)'
        )
        self._current_address = (self._current_address + 1) & 0xff
        high_byte = self._read_byte_from_current_address(
            'Fetch Effective Address high-byte (ADH) @ (00, BAL + X + 1)'
        )
        self._current_address = (high_byte << 8) | low_byte
        if self._write_buffer:
            self._current_data = self._write_buffer.pop()
            return self._write_byte_to_current_address('Write DATA @ (ADH, ADL)')

        return self._read_byte_from_current_address('Fetch DATA @ (ADH, ADL)')

    def _ind_y_mode_fetch_write_data(self) -> int:
        self._append_to_first_micro_desc('(zp),y')
        self._current_address = self._read_next_program_byte(
            'Fetch Zero-Page Inderect Address (IAL) @ PC + 1'
        )
        self._add_disasm_token(f'(${self._current_address:02X}),Y')
        low_byte = self._read_byte_from_current_address(
            'Fetch Base Address low-byte (BAL) @ (00, IAL)'
        ) + self._registers['Y']
        self._current_address = (self._current_address + 1) & 0xff
        high_byte = self._read_byte_from_current_address(
            'Fetch Base Address high-byte (BAH) @ (00, IAL + 1)'
        )
        self._current_address = (high_byte << 8) | (low_byte & 0xff)
        value = self._read_byte_from_current_address(
            'Fetch DATA @ (BAH, BAL + Y)'
        )
        if low_byte >> 8 or self._write_buffer:
            self._cycle_log[-1][0] += ' [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff

            if self._write_buffer:
                self._current_data = self._write_buffer.pop()
                value = self._write_byte_to_current_address('Write DATA @ (BAH + C, BAL + Y)')
            else:
                value = self._read_byte_from_current_address(
                    'Fetch DATA @ (BAH + 1, BAL + Y)'
                )

        return value


    """
    #    
    #    OP CODE IMPLEMENTATIONS
    #    
    """
    def _inst_adc_sbc(self):
        """
        [ADC] Add Memory to Accumulator with Carry
        [SBC] Subtract Memory From Accumulator with Borrow
        """
        subtract = self._current_data >> 7
        opcode = 'SBC' if subtract else 'ADC'
        self._set_disasm_token(opcode)
        self._append_to_first_micro_desc(opcode + ' ')

        value = self._fetch_write_data()

        # Convert to 1's complement when subtracting
        value = (value ^ (0xff * subtract)) + self._get_carry_flag()

        result = self._registers['ACC'] + value

        self._set_carry_flag(result >> 8)
        self._set_zero_flag(result & 0xff)
        self._set_overflow_flag((self._registers['ACC']^result) & (value^result) & 0x80)
        self._set_negative_flag(result & 0b10000000)
        self._registers['ACC'] = result & 0xff

    def _inst_bit_test(self) -> None:
        """
        [BIT] Test Bits in Memory with Accumulator
        """
        self._append_to_first_micro_desc('BIT ')
        self._set_disasm_token('BIT')

        value = self._fetch_write_data()

        self._set_negative_flag(value >> 7)
        self._set_overflow_flag(value & 0b01000000)
        self._set_zero_flag(value & self._registers['ACC'])

    _BRANCH_OP_CODES = ('BPL', 'BMI', 'BVC', 'BVS', '')
    _BRANCH_FLAG_BITS = (7, 6, 0, 1)
    def _inst_branch(self) -> None:
        """
        0[BCC] Branch on Carry Clear
        1[BCS] Branch on Carry Set
        2[BEQ] Branch on Result Zero (Zero Set)
        3[BMI] Branch on Result Minus (Negative Set)
        4[BNE] Branch on Result Not Zero (Zero Clear)
        5[BPL] Branch on Result Plus (Negative Clear)
        6[BVC] Branch on Overflow Clear
        7[BVS] Branch on Overflow Set
        """
        opcode_int = self._current_data >> 5
        opcode_str = MOS6502._BRANCH_OP_CODES[opcode_int]
        self._append_to_first_micro_desc(opcode_str)
        self._set_disasm_token(opcode_str)

        offset = self._read_next_program_byte('Fetch Branch Offset @ PC + 1')

        flag_bit = MOS6502._BRANCH_FLAG_BITS[opcode_int >> 1]
        flag_status = (self._registers['P'] >> flag_bit) & 1
        branch_taken = not flag_status ^ (opcode_int & 1)

        if branch_taken:
            self._cycle_log[-1][0] += ' [BRANCH TO PC + 2 + Offset '
            relative_offset = (offset ^ 0x80) - 0x80 # Convert from unsigned byte to signed byte
            pcl = self._registers['PCL']
            self._registers['PCL'] = (pcl + offset) & 0xff

            if pcl + relative_offset != self._registers['PCL']: # Page was crossed
                self._cycle_log[-1][0] += 'with Page-Cross]'
                self._read_next_program_byte(
                    'Fetch OP CODE @ PC + 2 + Offset without Page-Cross [DISCARDED]',
                    advance=False
                )
                if relative_offset < 0:
                    self._registers['PCH'] = (self._registers['PCH'] - 1) & 0xff
                else:
                    self._registers['PCH'] = (self._registers['PCH'] + 1) & 0xff

            else: # No page was crossed
                self._cycle_log[-1][0] += 'without Page-Cross]'

        else:
            self._cycle_log[-1][0] += ' [BRANCH IGNORED]'

    _BREAK_OP_CODES = (
        ('BRK', 0xFFFE),
        ('IRQ', 0xFFFE),
        ('NMI', 0xFFFA),
        ('RES', 0xFFFC)
    )
    def _inst_break(self, brk_type: int=0) -> None:
        """
        [BRK] Break Operation
        [IRQ] Interrupt Request
        [NMI] 
        [RES] Reset Operation
        
        "brk_type" argument:
            0: BRK
            1: IRQ
            2: NMI
            3: RES
        """
        self._set_disasm_token(MOS6502._BREAK_OP_CODES[brk_type][0])
        self._append_to_first_micro_desc(MOS6502._BREAK_OP_CODES[brk_type][0])
        old_p = self._registers['P']
        self._registers['P'] = 0b00110100
        int_vector = MOS6502._BREAK_OP_CODES[brk_type][1]

        if brk_type:
            self._set_break_flag(0)
            address = ((self._registers['PCH'] << 8) | self._registers['PCL']) - 1
            self._registers['PCL'] = address & 0xff
            self._registers['PCH'] = (address & 0xff00) >> 8
            self._read_next_program_byte('Fetch DATA @ PC [DISCARDED]')
        else:
            self._set_break_flag(1)
            self._read_next_program_byte('Fetch DATA @ PC + 1 [DISCARDED]')

        self._current_address = 0x10 | self._registers['S']
        self._current_data = self._registers['PCH']
        self._write_byte_to_current_address('Write PC high-byte to stack @ S')
        self._registers['S'] = (self._registers['S'] - 1) & 0xff

        self._current_address = 0x10 | self._registers['S']
        self._current_data = self._registers['PCL']
        self._write_byte_to_current_address('Write PC low-byte to stack @ S - 1')
        self._registers['S'] = (self._registers['S'] - 1) & 0xff

        self._current_address = 0x10 | self._registers['S']
        self._current_data = old_p
        self._write_byte_to_current_address('Write P to stack @ S - 2')
        self._registers['S'] = (self._registers['S'] - 1) & 0xff

        self._current_address = int_vector
        adl = self._read_byte_from_current_address(
            f'Fetch Interrup Vector low-byte (ADL) @ ${self._current_address:04X}'
        )
        self._current_address = int_vector + 1
        adh = self._read_byte_from_current_address(
            f'Fetch Interrup Vector high-byte (ADH) @ ${self._current_address:04X}'
        )

        self._registers['PCL'] = adl
        self._registers['PCH'] = adh


    def _inst_clear_set_flag(self) -> None:
        """
        [CLC] Clear Carry Flag
        [CLD] Clear Decimal Mode
        [CLI] Clear Interrupt Disable Bit
        [CLV] Clear Overflow Flag
        [SEC] Set Carry Flag
        [SED] Set Decimal Mode
        [SEI] Set Interrupt Disable Bit
        """
        opcode = ''
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
            }[reg](set_value)

        self._set_disasm_token(opcode)
        self._append_to_first_micro_desc(opcode)
        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)

    def _inst_compare(self) -> None:
        """
        [CMP] Compare Memory and Accumulator
        [CPX] Compare Memory and Index X
        [CPY] Compare Memory and Index Y
        """
        opcode = (
            ('CMP','ACC') if self._current_data & 1
            else ('CPX','X') if self._current_data & 0b00100000
            else ('CPY','Y')
        )
        self._set_disasm_token(opcode[0])
        self._append_to_first_micro_desc(opcode[0] + ' ')

        # Coerce OP Code to be in a nice arrangement for mode detection.
        # A low-byte of 0 is not defined in our data fetch function, so
        # add 2 so that it can be detected as IMMEDIATE addressing mode
        if not self._current_data & 0x0F:
            self._current_data += 2

        value = self._fetch_write_data()

        # Convert to 2's complement to subtract
        value = (value ^ 0xff) + 1

        result = self._registers[opcode[1]] + value

        self._set_negative_flag(result & 0b10000000)
        self._set_zero_flag(result & 0xff)
        self._set_carry_flag(result >> 8)

    def _inst_inc_dec_xy(self) -> None:
        """
        [DEX] Decrement X by 1
        [DEY] Decrement Y by 1
        [INX] Increment X by 1
        [INY] Increment Y by 1
        """
        index = 'X' if self._current_data >= 0xCA else 'Y'
        inc = self._current_data in (0xE8, 0xC8)
        opcode = ('IN' if inc else 'DE') + index
        self._set_disasm_token(opcode)

        self._registers[index] += 2 * inc - 1
        self._registers[index] &= 0xff
        self._set_zero_flag(self._registers[index])
        self._set_negative_flag(self._registers[index] >> 7)
        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)
        self._append_to_first_micro_desc(opcode)

    def _inst_jump(self) -> None:
        """
        [JMP] Jump Operation
        """
        self._set_disasm_token('JMP')

        if self._current_data == 0x4C: # Absolute addressing
            self._append_to_first_micro_desc('JMP a')
            adl = self._read_next_program_byte('Fetch Jump Address low-byte (ADL) @ PC + 1')
            adh = self._read_next_program_byte('Fetch Jump Address high-byte (ADH) @ PC + 2')
            self._registers['PCL'] = adl
            self._registers['PCH'] = adh
            self._add_disasm_token(f'${(adh << 8) | adl:04X}')
            return

        # Indirect addressing
        self._append_to_first_micro_desc('JMP (a)')
        ial = self._read_next_program_byte('Fetch Indirect Address low-byte (IAL) @ PC + 1')
        iah = self._read_next_program_byte('Fetch Indirect Address high-byte (IAH) @ PC + 2')
        self._add_disasm_token(f'(${(iah << 8) | ial:04X})')
        adl = self._read_next_program_byte('Fetch Jump Address low-byte (ADL) @ (IAH, IAL)')
        adh = self._read_next_program_byte('Fetch Jump Address high-byte (ADH) @ (IAH, IAL + 1)')
        self._registers['PCL'] = adl
        self._registers['PCH'] = adh

    def _inst_jump_to_subroutine(self) -> None:
        """
        [JSR] Jump to Subroutine
        """
        self._set_disasm_token('JSR')
        self._append_to_first_micro_desc('JSR a')

        adl = self._read_next_program_byte('Fetch Subroutine Address low-byte (ADL) @ PC + 1')

        self._current_address = 0x10 | self._registers['S']
        self._read_byte_from_current_address('Fetch DATA from stack @ S [DISCARDED]')
        self._current_data = self._registers['PCH']
        self._write_byte_to_current_address('Write PC high-byte to stack @ S')
        self._registers['S'] = (self._registers['S'] - 1) & 0xff

        self._current_address = 0x10 | self._registers['S']
        self._current_data = self._registers['PCL']
        self._write_byte_to_current_address('Write PC low-byte to stack @ S - 1')
        self._registers['S'] = (self._registers['S'] - 1) & 0xff

        adh = self._read_next_program_byte('Fetch Subroutine Address high-byte (ADH) @ PC + 2')
        self._registers['PCL'] = adl
        self._registers['PCH'] = adh

        self._add_disasm_token(f'${(adh << 8) | adl:04X}')

    def _inst_load_from_memory(self) -> None:
        """
        [LDA] Load Accumulator with Memory
        [LDX] Load Index X with Memory
        [LDY] Load Index Y with Memory
        """

        opcode = (
            ('LDA', 'ACC') if self._current_data & 1
            else ('LDX', 'X') if self._current_data & 2
            else ('LDY', 'Y')
        )
        self._set_disasm_token(opcode[0])
        self._append_to_first_micro_desc(opcode[0] + ' ')

        # Coerce OP Code to be in a nice arrangement for mode detection.
        # A low-byte of 0 is not defined in our data fetch function, so
        # add 2 so that it can be detected as IMMEDIATE addressing mode
        if not self._current_data & 0x0F:
            self._current_data += 2

        if self._current_data == 0xB6: # Handle special case of "LDX zp,y"
            value = self._zp_y_mode_fetch_write_data()
        else:
            value = self._fetch_write_data()

        self._registers[opcode[1]] = value
        self._set_negative_flag(value >> 7)
        self._set_zero_flag(value)

    def _inst_logic(self) -> None:
        """
        [AND] "AND" Memory with Accumulator
        [EOR] "XOR" Memory with Accumulator
        [ORA] "OR" Memory with Accumulator
        """
        opcode_int = (self._current_data >> 8) & 0b110
        opcode_str = 'ORA' if not opcode_int else 'AND' if opcode_int == 2 else 'XOR'
        self._set_disasm_token(opcode_str)
        self._append_to_first_micro_desc(opcode_str + ' ')

        value = self._fetch_write_data()

        acc = self._registers['ACC']
        result = (acc|value) if not opcode_int else (acc&value) if opcode_int == 2 else (acc^value)

        self._registers['ACC'] = result
        self._set_negative_flag(result >> 7)
        self._set_zero_flag(result)

    def _inst_nop(self) -> None:
        """
        [NOP] No Operation
        """
        self._set_disasm_token('NOP')
        self._append_to_first_micro_desc('NOP')
        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)

    _PUSH_PULL_OP_CODES = (
        ('P', 0, 'PHP'),
        ('P', 1, 'PLP'),
        ('ACC', 0, 'PHA'),
        ('ACC', 1, 'PLA'),
    )
    def _inst_push_pull_stack(self) -> None:
        """
        [PHA] Push Accumulator on Stack
        [PHP] Push Status Register on Stack
        [PLA] Pull Accumulator from Stack
        [PLP] Pull Status Register from Stack
        """
        reg, read, opcode_str = MOS6502._PUSH_PULL_OP_CODES[self._current_data >> 5]
        self._set_disasm_token(opcode_str)
        self._append_to_first_micro_desc(opcode_str)

        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)
        self._current_address = 0x10 | self._registers['S']

        if read:
            self._read_byte_from_current_address('Fetch DATA from stack @ S [DISCARDED]')
            self._registers['S'] = (self._registers['S'] + 1) & 0xff
            self._current_address = 0x10 | self._registers['S']
            self._registers[reg] = self._read_byte_from_current_address(
                f'Fetch {reg} from stack @ S + 1'
            )

            if self._current_address >> 6: # Accumulator pulled
                self._set_negative_flag(self._registers['ACC'] >> 7)
                self._set_zero_flag(self._registers['ACC'])

            else: # Processor Status Register pulled
                self._registers['P'] &= 0b11001111 # Ignore BRK flag and Bit 5
        else:
            self._current_data = self._registers[reg]
            self._write_byte_to_current_address(f'Write {reg} to stack @ S')
            self._registers['S'] = (self._registers['S'] - 1) & 0xff

    _RETURN_OP_CODES = (None, None, 'RTI', 'RTS')
    def _inst_return(self) -> None:
        """
        [RTI] Return from Interrupt
        [RTS] Return from Subroutine
        """
        opcode_str = MOS6502._RETURN_OP_CODES[self._current_data >> 5]
        self._set_disasm_token(opcode_str)
        self._append_to_first_micro_desc(opcode_str)

        self._read_next_program_byte('Fetch DATA @ PC + 1 [DISCARDED]', advance=False)
        self._current_address = 0x10 | self._registers['S']
        self._read_byte_from_current_address('Fetch DATA from stack @ S [DISCARDED]')

        self._registers['S'] = (self._registers['S'] + 1) & 0xff
        self._current_address = 0x10 | self._registers['S']

        if self._current_data == 0x40: # Return from Interrupt
            self._registers['P'] = self._read_byte_from_current_address(
                'Fetch P from stack @ S + 1'
            ) & 0b11001111 # Ignore BRK flag and Bit 5

            self._registers['S'] = (self._registers['S'] + 1) & 0xff
            self._current_address = 0x10 | self._registers['S']
            self._registers['PCL'] = self._read_byte_from_current_address(
                'Fetch PCL from stack @ S + 2'
            )

            self._registers['S'] = (self._registers['S'] + 1) & 0xff
            self._current_address = 0x10 | self._registers['S']
            self._registers['PCH'] = self._read_byte_from_current_address(
                'Fetch PCH from stack @ S + 3'
            )
            return

        # Return from Subroutine
        self._registers['PCL'] = self._read_byte_from_current_address(
            'Fetch PC low-byte from stack (PCL) @ S + 1'
        )

        self._registers['S'] = (self._registers['S'] + 1) & 0xff
        self._current_address = 0x10 | self._registers['S']
        self._registers['PCH'] = self._read_byte_from_current_address(
            'Fetch PC high-byte from stack (PCH) @ S + 2'
        )

        self._read_next_program_byte('Fetch DATA @ (PCH, PCL) [DISCARDED]')

    _READ_MOD_WRITE_OPS = ('ASL', 'ROL', 'LSR', 'ROR', None, None, 'DEC', 'INC')
    def _inst_read_mod_write(self) -> None:
        """
        [ASL] Arithmetic Shift Left by 1 Bit
        [DEC] Decrement Memory by 1
        [INC] Increment Memory by 1
        [LSR] Logic Shift Right by 1 Bit
        [ROL] Rotate 1 Bit Left
        [ROR] Rotate 1 Bit Right
        """
        opcode_int = self._current_data >> 5
        opcode_str = MOS6502._READ_MOD_WRITE_OPS[opcode_int]
        self._set_disasm_token(opcode_str)
        self._append_to_first_micro_desc(opcode_str + ' ')
        mode_low = self._current_data & 0x0f

        # Retrieve value first
        value = self._fetch_write_data(no_skip=True)

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

        self._set_zero_flag(value)
        self._set_negative_flag(value >> 7)

        # Execute final steps for accumulator mode of address
        if mode_low == 0x0A:
            self._registers['ACC'] = value
            self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)
            return

        # Execute final steps for other modes
        micro_desc_msg = self._cycle_log[-1][0][5:]
        self._write_byte_to_current_address('Write' + micro_desc_msg)
        self._current_data = value
        self._write_byte_to_current_address('Write Modified' + micro_desc_msg)

    def _inst_store_in_memory(self) -> None:
        """
        [STA] Store Accumulator in Memory
        [STX] Store Index X in Memory
        [STY] Store Index Y in Memory
        """
        opcode = (
            ('STA', 'ACC') if self._current_data & 1
            else ('STX', 'X') if self._current_data & 2
            else ('STY', 'Y')
        )
        self._set_disasm_token(opcode[0])
        self._append_to_first_micro_desc(opcode[0] + ' ')

        self._write_buffer.append(self._registers[opcode[1]])

        if self._current_data == 0x96: # Handle special case of "STX zp,y"
            self._zp_y_mode_fetch_write_data()
        else:
            self._fetch_write_data()

    def _inst_transfer(self) -> None:
        """
        [TAX] Transfer Accumulator to Index X
        [TAY] Transfer Accumulator to Index Y
        [TSX] Transfer Stack Pointer to Index X
        [TXA] Transfer Index X to Accumulator
        [TXS] Transfer Index X to Stack Pointer
        [TYA] Transfer Index Y to Accumulator
        """
        opcode = {
            0xAA: 'TAX',
            0xA8: 'TAY',
            0xBA: 'TSX',
            0x8A: 'TXA',
            0x9A: 'TXS',
            0x98: 'TYA',
        }[self._current_data]

        self._append_to_first_micro_desc(opcode)
        self._set_disasm_token(opcode)
        src, dst = ('ACC' if s == 'A' else s for s in opcode[1:])

        self._registers[dst] = self._registers[src]
        if self._current_data != 0x9A:
            self._set_negative_flag(self._registers[dst] >> 7)
            self._set_zero_flag(self._registers[dst])
        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)
