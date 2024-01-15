"""
Simulator definitions and functions for the main 6502 micro processor
"""
from py6502sim import Component

class MOS6502:
    """
    Class definition for the main MOS 6502 processor

    Based on the 1975 preliminary revision of the data sheet for the MCS6502 chip
    """
    def __init__(self, memory: Component) -> None:
        self._registers = {
            'ACC': 0,   # Accumulator
            'X': 0,     # Index Register X
            'Y': 0,     # Index Register Y
            'PCL': 0,   # Program Counter Low-byte   
            'PCH': 0,   # Program Counter High-byte

            'S': 0,
            # Stack Pointer S is always "zero-paged". The pointer is always technically a 9-bit
            # number where the bit 9 is always "1" and the bits 1 - 8 provide the 8-bit
            # address in the stack. I.e. S always points to addresses in the range 0x0100 ~ 0x01FF.
            # Our implementation will treat S as 8-bit, and assume it is always offset to 0x01XX.

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
            (0x69, 0x6D, 0x65, 0x61, 0x71, 0x75, 0x7D, 0x79): self._inst_adc_sbc,

            # [SBC] Subtract Memory From Accumulator with Borrow
            (0xE9, 0xED, 0xE5, 0xE1, 0xF1, 0xF5, 0xFD, 0xF9): self._inst_adc_sbc,
        }

        # This is easier to access through code
        self._instructions = dict(
            (code, op) for code_list, op in instructions.items() for code in code_list
        )

        self._memory = memory
        self._current_data = 0
        self._current_address = 0
        self._current_op = ''

        # Cycle log will contain a list of tuples in the form:
        # (
        #     address,
        #     data,
        #     read_write_bar,
        #     disassembled string,
        #     status register (LAST MICRO-INSTRUCTION ONLY)
        # )
        self._cycle_log: list[list] = []

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

    def _read_byte(self) -> int:
        self._current_data = self._memory.execute(self._current_address, self._current_data, 1)
        self._cycle_log.append([
            self._current_address,
            self._current_data,
            'READ',
            self._current_op
        ])
        return self._current_data

    def _write_byte(self) -> int:
        self._current_data = self._memory.execute(self._current_address, self._current_data, 0)
        self._cycle_log.append([
            self._current_address,
            self._current_data,
            'WRITE',
            self._current_op
        ])
        return self._current_data

    def _read_next_program_byte(self, advance: bool=True) -> int:
        self._current_address = (self._registers['PCH'] << 8) | self._registers['PCL']
        address = self._current_address + (1 if advance else 0)
        self._registers['PCL'] = address & 0xff
        self._registers['PCH'] = (address & 0xff00) >> 8
        return self._read_byte()

    def _inst_adc_sbc(self):
        """
        Executes either of the following instructions:

        [ADC] Add Memory to Accumulator with Carry
        [SBC] Subtract Memory From Accumulator with Borrow
        """
        value = 0
        subtract = (self._current_data >> 7) & 1
        base_inst = self._current_data & 0x7f
        self._current_op = 'ADC ' if not subtract else 'SBC '

        if base_inst == 0x69: # Immediate
            value = self._read_next_program_byte()
            self._current_op += f'#${value:02X}'

        elif base_inst == 0x6D: # Absolute
            low_byte = self._read_next_program_byte()
            high_byte = self._read_next_program_byte()
            self._current_address = (high_byte << 8) | low_byte
            value = self._read_byte()
            self._current_op += f'${self._current_address:04X}'

        elif base_inst == 0x65: # Zero Page
            low_byte = self._read_next_program_byte()
            self._current_address = low_byte
            value = self._read_byte()
            self._current_op += f'${self._current_address:02X}'

        elif base_inst == 0x61: # Indexed Indirect Addressing [(Indirect, X)]
            self._current_address = self._read_next_program_byte()
            self._current_op += f'(${self._current_address:02X},X)'
            self._read_byte()
            self._current_address = (self._current_address + self._registers['X']) & 0xff
            low_byte = self._read_byte()
            self._current_address = (self._current_address + 1) & 0xff
            high_byte = self._read_byte()
            self._current_address = (high_byte << 8) | low_byte
            value = self._read_byte()

        elif base_inst == 0x71: # Indirect Indexed Addressing [(Indirect), Y]
            self._current_address = self._read_next_program_byte()
            self._current_op += f'(${self._current_address:02X}),Y'
            low_byte = self._read_byte() + self._registers['Y']
            self._current_address = (self._current_address + 1) & 0xff
            high_byte = self._read_byte()
            self._current_address = (high_byte << 8) | (low_byte & 0xff)
            value = self._read_byte()
            if low_byte >> 8:
                self._current_address = ((high_byte << 8) + low_byte) & 0xffff
                value = self._read_byte()

        elif base_inst == 0x75: # Zero Page, X
            self._current_address = self._read_next_program_byte()
            self._current_op += f'${self._current_address:02X},X'
            self._read_byte()
            self._current_address = (self._current_address + self._registers['X']) & 0xff
            value = self._read_byte()

        elif base_inst == 0x7D: # Absolute, X
            low_byte = self._read_next_program_byte() + self._registers['X']
            high_byte = self._read_next_program_byte()
            self._current_op += f'${high_byte:02X}{low_byte-self._registers['X']:02X},X'
            self._current_address = (high_byte << 8) | (low_byte & 0xff)
            value = self._read_byte()
            if low_byte >> 8:
                self._current_address = ((high_byte << 8) + low_byte) & 0xffff
                value = self._read_byte()

        elif base_inst == 0x79: # Absolute, Y
            low_byte = self._read_next_program_byte() + self._registers['Y']
            high_byte = self._read_next_program_byte()
            self._current_op += f'${high_byte:02X}{low_byte-self._registers['Y']:02X},Y'
            self._current_address = (high_byte << 8) | (low_byte & 0xff)
            value = self._read_byte()
            if low_byte >> 8:
                self._current_address = ((high_byte << 8) + low_byte) & 0xffff
                value = self._read_byte()

        for log in self._cycle_log:
            log[-1] = self._current_op

        # Convert to 1's complement when subtracting
        value ^= 0xff * subtract + self._get_carry_flag()

        result = self._registers['ACC'] + value

        self._set_carry_flag(result >> 8)
        self._set_zero_flag(result & 0xff)
        self._set_overflow_flag((self._registers['ACC']^result) & (value^result) & 0x80)
        self._set_negative_flag((result >> 7) & 1)
        self._registers['ACC'] = result & 0xff

        self._cycle_log[-1].append(self._registers)

    def reset(self) -> None:
        self._registers['ACC'] = 0
        self._registers['X'] = 0
        self._registers['Y'] = 0
        self._registers['PCL'] = 0xfc
        self._registers['PCH'] = 0xff
        self._registers['S'] = 0xff
        self._registers['P'] = 0b00100100

    def start_step(self) -> None:
        pass

    def finish_step(self) -> None:
        pass

    def halt(self) -> None:
        pass

    def run(self) -> None:
        pass
