"""
Simulator definitions and functions for the main 6502 micro processor
"""
from py6502sim import Component

# TODO: Implement Decimal Mode in ADC and SBC

class MOS6502:
    """
    Class definition for the main MOS 6502 processor

    Based on the 1976 revision of the MCS6502 chip
    """
    def __init__(self, memory: Component) -> None:
        self._memory = memory
        self._current_data = 0
        self._current_address = 0
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

        # This is easier to type
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
            # [LSR] Logic Shift Right by 1 Bit
            # [ROL] Rotate 1 Bit Left
            # [ROR] Rotate 1 Bit Right
            (0x0E, 0x06, 0x0A, 0x16, 0x1E,
             0x4E, 0x46, 0x4A, 0x56, 0x5E,
             0x2E, 0x26, 0x2A, 0x36, 0x3E,
             0x6E, 0x66, 0x6A, 0x76, 0x7E): self._inst_asl_lsr_rol,

            # [CLC] Clear Carry Flag
            # [CLD] Clear Decimal Mode
            # [CLI] Clear Interrupt Disable Bit
            # [CLV] Clear Overflow Flag
            # [SEC] Set Carry Flag
            # [SED] Set Decimal Mode
            # [SEI] Set Interrupt Disable Bit
            (0x18, 0xD8, 0x58, 0xB8, 0x38, 0xF8, 0x78): self._inst_clear_set_flag,

            # [DEX] Decrement X by 1
            # [DEY] Decrement Y by 1
            # [INX] Increment X by 1
            # [INY] Increment Y by 1
            (0xCA, 0x88, 0xE8, 0xC8): self._inst_inc_dec_xy,

            # [TAX] Transfer Accumulator to Index X
            # [TAY] Transfer Accumulator to Index Y
            # [TSX] Transfer Stack Pointer to Index X
            # [TXA] Transfer Index X to Accumulator
            # [TXS] Transfer Index X to Stack Pointer
            # [TYA] Transfer Index Y to Accumulator
            (0xAA, 0xA8, 0xBA, 0x8A, 0x9A, 0x98): self._inst_transfer,

            # [NOP] No Operation
            (0xEA,): self._inst_nop,
        }

        # This is easier to access through code
        self._instructions = dict(
            (code, op) for code_list, op in instructions.items() for code in code_list
        )


    """
    #    
    #    PUBLIC FACING CONTROL FUNCTIONS
    #    
    """
    def reset(self) -> None:
        """
        Runs the processor through the reset sequence
        """
        self._registers['ACC'] = 0
        self._registers['X'] = 0
        self._registers['Y'] = 0
        self._registers['PCL'] = 0xfc
        self._registers['PCH'] = 0xff
        self._registers['S'] = 0xff
        self._registers['P'] = 0b00100100

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

    def _set_disasm_tokens(self, token_str: str) -> None:
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

    def _write_byte(self, micro_desc: str) -> int:
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
        address = self._current_address + (1 if advance else 0)
        self._registers['PCL'] = address & 0xff
        self._registers['PCH'] = (address & 0xff00) >> 8
        return self._read_byte_from_current_address(micro_desc)


    """
    #    
    #    DATA FETCH FUNCTIONS FOR VARIOUS ADDRESSING MODE 
    #    
    """
    def _fetch_data(self, no_skip: bool=False) -> int:
        value = None
        mode_high = self._current_data & 0x10
        mode_low = self._current_data & 0x0F

        if mode_low in [0x02, 0x09]:
            value = (
                self._abs_y_mode_fetch_data(no_skip) if mode_high # Absolute, Y
                else self._immediate_mode_fetch_data()            # Immediate
            )

        elif mode_low in [0x0C, 0x0D, 0x0E]:
            value = (
                self._abs_x_mode_fetch_data(no_skip) if mode_high # Absolute, X
                else self._absolute_mode_fetch_data()             # Absolute
            )

        elif mode_low in [0x04, 0x05, 0x06]:
            value = (
                self._zp_x_mode_fetch_data() if mode_high         # Zero Page, X
                else self._zero_page_mode_fetch_data()            # Zero Page
            )

        elif mode_low == 0x0A:
            value = self._accumulator_mode_fetch_data()           # Accumulator

        elif mode_low == 0x01:
            value = (
                self._ind_y_mode_fetch_data() if mode_high        # (Indirect), Y
                else self._ind_x_mode_fetch_data()                # (Indirect, X)
            )

        return value

    def _immediate_mode_fetch_data(self) -> int:
        self._append_to_first_micro_desc('#')
        value = self._read_next_program_byte('Fetch DATA @ PC + 1')
        self._add_disasm_token(f'#${value:02X}')
        return value

    def _absolute_mode_fetch_data(self) -> int:
        self._append_to_first_micro_desc('a')
        low_byte = self._read_next_program_byte(
            'Fetch Effective Address low-byte (ADL) @ PC + 1'
        )
        high_byte = self._read_next_program_byte(
            'Fetch Effective Address high-byte (ADH) @ PC + 2'
        )
        self._current_address = (high_byte << 8) | low_byte
        self._add_disasm_token(f'${self._current_address:04X}')
        return self._read_byte_from_current_address('Fetch DATA @ (ADH, ADL)')

    def _zero_page_mode_fetch_data(self) -> int:
        self._append_to_first_micro_desc('zp')
        low_byte = self._read_next_program_byte(
            'Fetch Effective Address low-byte (ADL) @ PC + 1'
        )
        self._current_address = low_byte
        self._add_disasm_token(f'${self._current_address:02X}')
        return self._read_byte_from_current_address('Fetch DATA @ (00, ADL)')

    def _accumulator_mode_fetch_data(self) -> int:
        self._append_to_first_micro_desc('ACC')
        self._add_disasm_token('ACC')
        return self._registers['ACC']

    def _zp_x_mode_fetch_data(self) -> int:
        self._append_to_first_micro_desc('zp,x')
        self._current_address = self._read_next_program_byte(
            'Fetch Zero-Page Base Address (BAL) @ PC + 1'
        )
        self._add_disasm_token(f'${self._current_address:02X},X')
        self._read_byte_from_current_address('Fetch DATA @ (00, BAL) [DISCARDED]')
        self._current_address = (self._current_address + self._registers['X']) & 0xff
        return self._read_byte_from_current_address(
            'Fetch DATA @ (00, BAL + X)'
        )

    def _zp_y_mode_fetch_data(self) -> int:
        self._append_to_first_micro_desc('zp,y')
        self._current_address = self._read_next_program_byte(
            'Fetch Zero-Page Base Address (BAL) @ PC + 1'
        )
        self._add_disasm_token(f'${self._current_address:02X},Y')
        self._read_byte_from_current_address('Fetch DATA @ (00, BAL) [DISCARDED]')
        self._current_address = (self._current_address + self._registers['Y']) & 0xff
        return self._read_byte_from_current_address(
            'Fetch DATA @ (00, BAL + Y)'
        )

    def _abs_x_mode_fetch_data(self, no_skip: bool=False) -> int:
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
        if no_skip or low_byte >> 8:
            self._cycle_log[-1][0] += ' [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
            value = self._read_byte_from_current_address(
                f'Fetch DATA @ (BAH + {"C" if no_skip else "1"}, BAL + X)'
            )
        return value

    def _abs_y_mode_fetch_data(self, no_skip: bool=False) -> int:
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
        if no_skip or low_byte >> 8:
            self._cycle_log[-1][0] += ' [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
            value = self._read_byte_from_current_address(
                f'Fetch DATA @ (BAH + {"C" if no_skip else "1"}, BAL + Y)'
            )
        return value

    def _ind_x_mode_fetch_data(self) -> int:
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
        return self._read_byte_from_current_address('Fetch DATA @ (ADH, ADL)')

    def _ind_y_mode_fetch_data(self) -> int:
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
        if low_byte >> 8:
            self._cycle_log[-1][0] += ' [DISCARDED]'
            self._current_address = ((high_byte << 8) + low_byte) & 0xffff
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
        self._set_disasm_tokens(opcode)
        self._append_to_first_micro_desc(opcode + ' ')

        value = self._fetch_data()

        # Convert to 1's complement when subtracting
        value ^= 0xff * subtract + self._get_carry_flag()

        result = self._registers['ACC'] + value

        self._set_carry_flag(result >> 8)
        self._set_zero_flag(result & 0xff)
        self._set_overflow_flag((self._registers['ACC']^result) & (value^result) & 0x80)
        self._set_negative_flag((result >> 7) & 1)
        self._registers['ACC'] = result & 0xff

    def _inst_asl_lsr_rol(self) -> None:
        """
        [ASL] Arithmetic Shift Left by 1 Bit
        [LSR] Logic Shift Right by 1 Bit
        [ROL] Rotate 1 Bit Left
        [ROR] Rotate 1 Bit Right
        """
        opcode_int = self._current_data >> 5
        opcode_str = ['ASL', 'ROL', 'LSR', 'ROR'][opcode_int]
        self._set_disasm_tokens(opcode_str)
        self._append_to_first_micro_desc(opcode_str + ' ')
        mode_low = self._current_data & 0x0f

        # Retrieve value first
        value = self._fetch_data(no_skip=True)

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
        else: # ROR
            temp_carry = value & 1
            value = (value >> 1) | (self._get_carry_flag() << 7)
            self._set_carry_flag(temp_carry)

        self._set_zero_flag(value)
        self._set_negative_flag((value >> 7) & 1)

        # Execute final steps for accumulator mode of address
        if mode_low == 0x0A:
            self._registers['ACC'] = value
            self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)
            return

        # Execute final steps for other modes
        micro_desc_msg = self._cycle_log[-1][0][5:]
        self._write_byte('Write' + micro_desc_msg)
        self._current_data = value
        self._write_byte('Write Modified' + micro_desc_msg)

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

        self._add_disasm_token(opcode)
        self._append_to_first_micro_desc(opcode)
        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)

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
        self._registers[index] += 2 * inc - 1
        self._set_zero_flag(self._registers[index])
        self._set_negative_flag((self._registers[index] >> 7) & 1)
        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)
        self._add_disasm_token(opcode)
        self._append_to_first_micro_desc(opcode)

    def _inst_logic(self) -> None:
        """
        [AND] "AND" Memory with Accumulator
        [EOR] "XOR" Memory with Accumulator
        [ORA] "OR" Memory with Accumulator
        """
        opcode_int = (self._current_data >> 8) & 0b110
        opcode_str = 'ORA' if not opcode_int else 'AND' if opcode_int == 2 else 'XOR'
        self._add_disasm_token(opcode_str)
        self._append_to_first_micro_desc(opcode_str + ' ')

        value = self._fetch_data()

        acc = self._registers['ACC']
        result = (acc|value) if not opcode_int else (acc&value) if opcode_int == 2 else (acc^value)

        self._registers['ACC'] = result
        self._set_negative_flag(result >> 7)
        self._set_zero_flag(result)

    def _inst_nop(self) -> None:
        """
        [NOP] No Operation
        """
        self._add_disasm_token('NOP')
        self._append_to_first_micro_desc('NOP')
        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)

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
        self._add_disasm_token(opcode)
        src, dst = ('ACC' if s == 'A' else s for s in opcode[1:])

        self._registers[dst] = self._registers[src]
        if self._current_data != 0x9A:
            self._set_negative_flag(self._registers[dst] >> 7)
            self._set_zero_flag(self._registers[dst])
        self._read_next_program_byte('Fetch OP CODE @ PC + 1 [DISCARDED]', advance=False)
