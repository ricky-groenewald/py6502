"""
6502 Assembler definitions and functions
"""
from ast import literal_eval
import re

# TODO:
#   * Symbols (tokenized, but not validated)
#   * Directives (not tokenized/implemented) (except .MOD)
#   * Forego own arith_eval and instead use python eval, but well escaped?

# NOTE:
#   * First versions of the assembler will be a very DUMB assembler
#   * I.e. Rudimentary directives, no linking, no optimizations, no illegal instructions, etc.
#   * Expressions only allow bitwise/integer arithmetic. No boolean logic accepted (yet)
#   * Symbols can only be set once
#   * The @ symbol will be used to reference the Program Counter

class AssemblySyntaxError(Exception):
    """
    Syntax error was encountered in the assembly code
    """

class TokenizerError(Exception):
    """
    An error has occured during tokenizing
    """

class Assembler:
    """
    Class definition for the 6502 assembler
    """
    OPERAND_REGEX = r'[%$0-9A-Z~^|<>&+\-\/\*\s\(\)]+'

    def __init__(self) -> None:
        self._tokens: dict[int, list] = {} # {offset1: tokens1, offset2: tokens2, ...}
        self._current_offset: int = 0
        self._labels: dict[str, int] = {} # {label: absolute address}
        self._symbols: dict[str, (int, str)] = {} # {symbol: expression}

    def _is_hex(self, hex_string: str) -> bool:
        return bool(re.fullmatch(r'[0-9a-fA-F]+', hex_string))

    def _parse_hex(self, hex_str: str) -> int:
        if self._is_hex(hex_str):
            return literal_eval(f'0x{hex_str}')

        raise TokenizerError(f'Invalid hexadecimal value: {hex_str}')

    def _is_bin(self, bin_string: str) -> bool:
        return bool(re.fullmatch(r'[01]+', bin_string))

    def _parse_bin(self, bin_str: str) -> int:
        if bin_str[0] == '%':
            if self._is_bin(bin_str[1:]):
                return literal_eval(f'0b{bin_str[1:]}')

            raise TokenizerError(f'Invalid binary value: {bin_str[1:]} -- '
                                 '(TIP: Use ".MOD" for the Modulo % operation)')

        if self._is_bin(bin_str[2:]):
            return literal_eval(f'0b{bin_str[2:]}')

        raise TokenizerError(f'Invalid binary value: {bin_str[2:]}')

    def _parse_numbers(self, asm_string: str) -> str:
        # We purposefully capture incorrect values

        # 0x00FF type
        asm_string = re.sub(
            r'(?<![a-zA-Z0-9])0x[a-zA-Z0-9]+',
            lambda x: self._parse_hex(x.group()[2:]),
            asm_string
        )

        # $00FF type
        asm_string = re.sub(
            r'(?<![a-zA-Z0-9])\$[a-zA-Z0-9]+',
            lambda x: self._parse_hex(x.group()[1:]),
            asm_string
        )

        # 0b1001 type or %1001 type
        asm_string = re.sub(
            r'(?<![a-zA-Z0-9])((%)|(0b))[a-zA-Z0-9]+',
            self._parse_bin,
            asm_string
        )

        # If there are still some straggling $ or % symbols
        if asm_string.count('$'):
            raise TokenizerError('$ symbols should be immediately followed by a hexadecimal value '
                                 'and not be preceded by other alpha-numeric characters')
        if asm_string.count('%'):
            raise TokenizerError('% symbols should be immediately followed by a binary value '
                                 'and not be preceded by other alpha-numeric characters\n'
                                 '(TIP: Use ".MOD" for the Modulo % operation)')

        return asm_string

    def _process_symbol(self, symbol_name: str, expression: str) -> None:
        if not expression or re.findall(r'[=:]+', expression):
            raise AssemblySyntaxError(
                'Invalid symbol declaration -- '
                'Symbol declarations should follow "SYMBOL = EXPRESSION"'
            )

        if self._is_hex(symbol_name):
            raise AssemblySyntaxError(f'Cannot use a hex value {symbol_name} as a symbol name')

        # Check validity of symbol name
        if not (
            symbol_name[0].isalpha() and
            symbol_name.isalnum()
        ):
            raise AssemblySyntaxError(
                f'Invalid symbol name: {symbol_name} -- '
                'Symbol names should only contain alpha-numeric characters, and the first '
                'character should be alphabetic'
            )

        if symbol_name in self._labels or symbol_name in self._symbols:
            raise AssemblySyntaxError(f'{symbol_name} already previously defined')

        if symbol_name in INSTRUCTION_MAP:
            raise AssemblySyntaxError(f'Cannot use opcode {symbol_name} as a symbol name')

        value = self._get_value(expression)

        self._symbols[symbol_name] = value

    def _process_label(self, label_token: str) -> None:
        # Is a valid label name
        if label_token[:-1].isalnum():
            label_name = label_token[:-1]

            if self._is_hex(label_name):
                raise AssemblySyntaxError(f'Cannot use a hex value {label_name} as a label name')

            if label_name in self._labels or label_name in self._symbols:
                raise AssemblySyntaxError(f'{label_name} already previously defined')

            if label_name in INSTRUCTION_MAP:
                raise AssemblySyntaxError(f'Cannot use opcode {label_name} as a label name')

            self._labels[label_name] = (
                len(self._tokens.setdefault(self._current_offset, [])) + self._current_offset
            )

        else:
            raise AssemblySyntaxError(
                f'Invalid label: {label_token} -- '
                'Labels should only use alpha-numeric characters with its first character '
                'being alphabetic, and end with a colon ":"'
            )


    def _process_directive(self, directive: str, operand: str) -> None:
        pass

    def _test_bitwise_validity(self, value1: int, value2: int) -> None:
        if not (-128 <= value1 <= 255 and -128 <= value2 <= 255):
            raise TokenizerError(
                'Number overflow -- Bitwise operations only operate on 8-bit values'
            )

    def _eval_arithmetic(self, arith_string: str) -> (str, int):
        # Using assembly operator precedence as defined in ca65's manual:
        # https://cc65.github.io/doc/ca65.html#ss4.1
        # EXCEPT: Shift left/right takes precedence over ^,&,.MOD,/,*

        # There should be no syntax errors here. If there are, the regexes are wrong.

        # Unary bitwise not
        # First test all the expressions, and then evaluate the values
        unot_regex = r'~[-+]?[0-9]+'
        for match in re.findall(unot_regex, arith_string):
            self._test_bitwise_validity(literal_eval(match[1:]), 0)
        arith_string = re.sub(
            unot_regex,
            lambda x: str((literal_eval(x[1:]) & 0xff) ^ 0xff),
            arith_string
        )

        # Unary low-byte
        # First test all the expressions, and then evaluate the values
        ulow_regex = r'(?<!<)<[-+]?[0-9]+'
        for match in re.findall(ulow_regex, arith_string):
            value = literal_eval(match[1:])
            if value < 0 or value > 0xffff:
                raise TokenizerError(
                    'Unary low-byte can only be obtained from positive 16-bit numbers'
                )
        arith_string = re.sub(
            ulow_regex,
            lambda x: str(literal_eval(x[1:]) & 0xff),
            arith_string
        )

        # Unary high-byte
        # First test all the expressions, and then evaluate the values
        uhigh_regex = r'(?<!>)>[-+]?[0-9]+'
        for match in re.findall(uhigh_regex, arith_string):
            value = literal_eval(match[1:])
            if value < 0 or value > 0xffff:
                raise TokenizerError(
                    'Unary low-byte can only be obtained from positive 16-bit numbers'
                )
        arith_string = re.sub(
            uhigh_regex,
            lambda x: str(literal_eval(x[1:]) & 0xff),
            arith_string
        )

        # Bitwise shift-left, Bitwise shift-right
        # First test for negative numbers then evaluate from left to right
        if re.search(r'((<<)|(>>))-[0-9]+', arith_string):
            raise TokenizerError('Bitwise shifting with a negative number')
        shift_regex = r'(?<![0-9])[-+]?[0-9]+((<<)|(>>))[+]?[0-9]+'
        while (match := re.search(shift_regex, arith_string)):
            op = '<<' if match.group().count('<<') else '>>'
            value1, value2 = [literal_eval(val) for val in match.group().split(op)]
            if op == '<<':
                result = value1 << value2
            else:
                result = value1 >> value2
            arith_string = re.sub(
                shift_regex,
                str(result),
                arith_string,
                count=1
            )

        # Bitwise XOR, Bitwise AND, Modulo, Division, Multiplication
        multi_regex = r'(?<![0-9])[-+]?[0-9]+[%/*&^][-+]?[0-9]+'
        while (match := re.search(multi_regex, arith_string)):
            op = re.search(r'[%/*&^]', match.group()).group()
            value1, value2 = [literal_eval(val) for val in match.group().split(op)]
            if op == '%':
                result = value1 % value2
            elif op == '/':
                result = value1 // value2
            elif op == '*':
                result = value1 * value2
            elif op == '&':
                self._test_bitwise_validity(value1, value2)
                result = value1 & value2
            else:
                self._test_bitwise_validity(value1, value2)
                result = value1 ^ value2
            arith_string = re.sub(
                multi_regex,
                str(result),
                arith_string,
                count=1
            )

        # Bitwise Or, Addition, Subtraction
        addsubor_regex = r'(?<![0-9])[-+]?[0-9]+[-+|][-+]?[0-9]+'
        while (match := re.search(addsubor_regex, arith_string)):
            op_match = re.search(r'(?<=[0-9])[-+|](?=[-+]?[0-9]+)', match.group())
            op = op_match.group()
            value1 = literal_eval(match.group()[:op_match.span()[0]])
            value2 = literal_eval(match.group()[op_match.span()[1]:])
            if op == '+':
                result = value1 + value2
            elif op == '-':
                result = value1 - value2
            else:
                self._test_bitwise_validity(value1, value2)
                result = value1 | value2
            arith_string = re.sub(
                addsubor_regex,
                str(result),
                arith_string,
                count=1
            )

        return literal_eval(arith_string)

    def _get_value(self, value_string: str) -> (str, int):
        # value_string should not contain any uppercase characters at this point

        # Substitute any named identifiers with their values
        # If a symbol is defined by other symbols, no change is made
        # Might contain illegal identifier names, so this should be handled later
        for named in set(re.findall(r'[A-Z0-9]', value_string)):
            if named in self._symbols and isinstance(self._symbols[named], int):
                value_string = value_string.replace(
                    named,
                    str(self._symbols[named])
                )
            elif named in self._labels:
                value_string = value_string.replace(
                    named,
                    str(self._labels[named])
                )

        # Repeatedly try to evaluate literal expressions in parentheses
        expressions = set(re.findall(r'\([^()]+\)', value_string))
        changed = True
        while expressions and changed:
            changed = False
            for exp in expressions:
                result = self._get_value(exp[1:-1])
                if isinstance(result, int):
                    value_string = value_string.replace(exp, str(result))
                    changed = True

            if changed:
                expressions = set(re.findall(r'\([^()]+\)', value_string))

        # Test if it is an arithmetic string, if not, return reduced string
        full_regex = r'([<>~+-]?[0-9]+)(([\^|%&+\-\/\*]|(<<)|(>>))([<>~+-]?[0-9]+))*'
        reduced_string = re.sub(r'[\s]+', '', value_string) # Remove whitespace
        if re.fullmatch(full_regex, reduced_string):
            return self._eval_arithmetic(reduced_string)

        return value_string

    def _tokenize_opcode(self, opcode: str, operand: str) -> None:
        implied_ops = [op for op, modes in INSTRUCTION_MAP.items() if modes[4] is not None]

        # An opcode with implied adressing mode was entered
        if opcode in implied_ops:
            # Should have no operands
            if operand:
                raise AssemblySyntaxError(
                    f'Opcode {opcode} does not take operands'
                )

            self._tokens.setdefault(self._current_offset, []).append(INSTRUCTION_MAP[opcode][4])
            return

        # Handle opcodes with operands

    def _tokenize_and_append(self, asm_string: str) -> None:
        """
        Tokenizes a line of text and appends the tokens to the instance's _tokens variable.

        This function should only be called with a single line of code as its argument
        """
        if asm_string.count('\n') > 1 or asm_string.find('\n') not in [-1, len(asm_string) - 1]:
            raise TokenizerError('Multiple lines fed into the tokenizer. Only supply single lines.')

        # Return on empty string
        if not asm_string.strip():
            return

        # Find comment index
        comment_index = asm_string.find(';')
        comment_index = len(asm_string) if comment_index < 0 else comment_index

        # We pass case-sensitive string in first to parse numbers to decimal
        # After parsing is complete, we will convert to uppercase
        asm_string = self._parse_numbers(asm_string[:comment_index].strip()).upper()

        # Since we have already handled all % characters, we can now
        # replace the .MOD operator with %
        asm_string = re.sub(r'\.MOD', '%', asm_string)

        # First check if symbols are being assigned
        if '=' in asm_string:
            self._process_symbol(*asm_string.strip().split('=', 1))

        string_split = asm_string.split()

        # Test if first token is potentially a label
        if string_split[0][-1] == ':':
            label_token = string_split.pop(0)
            self._process_label(label_token)

        # Line only had a label or comment
        if not string_split:
            return

        # Handle any possible directives
        if string_split[0][0] == '.':
            self._process_directive(string_split[0], ' '.join(string_split[1:]))
            return

        # Handle opcodes
        if string_split[0] in INSTRUCTION_MAP:
            self._tokenize_opcode(string_split[0], ' '.join(string_split[1:]))
            return

        raise TokenizerError(f'Unrecognized statement: {' '.join(string_split)}')

    def _validate_symbols(self) -> None:
        pass

    def _assemble_tokens(self) -> list[int]:
        pass

    def assemble_from_file(self, filename: str) -> bytes:
        self._tokens = {}
        self._labels = {}
        pass

    def assemble_from_string(self, asm_string: str) -> bytes:
        self._tokens = {}
        self._labels = {}
        pass


INSTRUCTION_MAP = {
#MNEMONIC: [ #  ,   a  ,   zp ,   Acc,   Imp, ($,X), ($),Y,  zp,X,   a,X,   a,Y,   Rel,   ($),  zp,Y]
    'ADC': [0x69,  0x6D,  0x65,  None,  None,  0x61,  0x71,  0x75,  0x7D,  0x79,  None,  None,  None],
    'AND': [0x29,  0x2D,  0x25,  None,  None,  0x21,  0x31,  0x35,  0x3D,  0x39,  None,  None,  None],
    'ASL': [None,  0x0E,  0x06,  0x0A,  None,  None,  None,  0x16,  0x1E,  None,  None,  None,  None],
    'BCC': [None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0x90,  None,  None],
    'BCS': [None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0xB0,  None,  None],
    'BEQ': [None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0xF0,  None,  None],
    'BIT': [None,  0x2C,  0x24,  None,  None,  None,  None,  None,  None,  None,  None,  None,  None],
    'BMI': [None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0x30,  None,  None],
    'BNE': [None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0xD0,  None,  None],
    'BPL': [None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0x10,  None,  None],
    'BRK': [None,  None,  None,  None,  0x00,  None,  None,  None,  None,  None,  None,  None,  None],
    'BVC': [None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0x50,  None,  None],
    'BVS': [None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0x70,  None,  None],
    'CLC': [None,  None,  None,  None,  0x18,  None,  None,  None,  None,  None,  None,  None,  None],
    'CLD': [None,  None,  None,  None,  0xD8,  None,  None,  None,  None,  None,  None,  None,  None],
    'CLI': [None,  None,  None,  None,  0x58,  None,  None,  None,  None,  None,  None,  None,  None],
    'CLV': [None,  None,  None,  None,  0xB8,  None,  None,  None,  None,  None,  None,  None,  None],
    'CMP': [0xC9,  0xCD,  0xC5,  None,  None,  0xC1,  0xD1,  0xD5,  0xDD,  0xD9,  None,  None,  None],
    'CPX': [0xE0,  0xEC,  0xE4,  None,  None,  None,  None,  None,  None,  None,  None,  None,  None],
    'CPY': [0xC0,  0xCC,  0xC4,  None,  None,  None,  None,  None,  None,  None,  None,  None,  None],
    'DEC': [None,  0xCE,  0xC6,  None,  None,  None,  None,  0xD6,  0xDE,  None,  None,  None,  None],
    'DEX': [None,  None,  None,  None,  0xCA,  None,  None,  None,  None,  None,  None,  None,  None],
    'DEY': [None,  None,  None,  None,  0x88,  None,  None,  None,  None,  None,  None,  None,  None],
    'EOR': [0x49,  0x4D,  0x45,  None,  None,  0x41,  0x51,  0x55,  0x5D,  0x59,  None,  None,  None],
    'INC': [None,  0xEE,  0xE6,  None,  None,  None,  None,  0xF6,  0xFE,  None,  None,  None,  None],
    'INX': [None,  None,  None,  None,  0xE8,  None,  None,  None,  None,  None,  None,  None,  None],
    'INY': [None,  None,  None,  None,  0xC8,  None,  None,  None,  None,  None,  None,  None,  None],
    'JMP': [None,  0x4C,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0x6C,  None],
    'JSR': [None,  0x20,  None,  None,  None,  None,  None,  None,  None,  None,  None,  None,  None],
    'LDA': [0xA9,  0xAD,  0xA5,  None,  None,  0xA1,  0xB1,  0xB5,  0xBD,  0xB9,  None,  None,  None],
    'LDX': [0xA2,  0xAE,  0xA6,  None,  None,  None,  None,  None,  None,  0xBE,  None,  None,  0xB6],
    'LDY': [0xA0,  0xAC,  0xA4,  None,  None,  None,  None,  0xB4,  0xBC,  None,  None,  None,  None],
    'LSR': [None,  0x4E,  0x46,  0x4A,  None,  None,  None,  0x56,  0x5E,  None,  None,  None,  None],
    'NOP': [None,  None,  None,  None,  0xEA,  None,  None,  None,  None,  None,  None,  None,  None],
    'ORA': [0x09,  0x0D,  0x05,  None,  None,  0x01,  0x11,  0x15,  0x1D,  0x19,  None,  None,  None],
    'PHA': [None,  None,  None,  None,  0x48,  None,  None,  None,  None,  None,  None,  None,  None],
    'PHP': [None,  None,  None,  None,  0x08,  None,  None,  None,  None,  None,  None,  None,  None],
    'PLA': [None,  None,  None,  None,  0x68,  None,  None,  None,  None,  None,  None,  None,  None],
    'PLP': [None,  None,  None,  None,  0x28,  None,  None,  None,  None,  None,  None,  None,  None],
    'ROL': [None,  0x2E,  0x26,  0x2A,  None,  None,  None,  0x36,  0x3E,  None,  None,  None,  None],
    'ROR': [None,  0x6E,  0x66,  0x6A,  None,  None,  None,  0x76,  0x7E,  None,  None,  None,  None],
    'RTI': [None,  None,  None,  None,  0x40,  None,  None,  None,  None,  None,  None,  None,  None],
    'RTS': [None,  None,  None,  None,  0x60,  None,  None,  None,  None,  None,  None,  None,  None],
    'SBC': [0xE9,  0xED,  0xE5,  None,  None,  0xE1,  0xF1,  0xF5,  0xFD,  0xF9,  None,  None,  None],
    'SEC': [None,  None,  None,  None,  0x38,  None,  None,  None,  None,  None,  None,  None,  None],
    'SED': [None,  None,  None,  None,  0xF8,  None,  None,  None,  None,  None,  None,  None,  None],
    'SEI': [None,  None,  None,  None,  0x78,  None,  None,  None,  None,  None,  None,  None,  None],
    'STA': [None,  None,  0x8D,  0x85,  None,  0x81,  0x91,  0x95,  0x9D,  0x99,  None,  None,  None],
    'STX': [None,  None,  0x8E,  0x86,  None,  None,  None,  None,  None,  None,  None,  None,  0x96],
    'STY': [None,  None,  0x8C,  0x84,  None,  None,  None,  0x94,  None,  None,  None,  None,  None],
    'TAX': [None,  None,  None,  None,  0xAA,  None,  None,  None,  None,  None,  None,  None,  None],
    'TAY': [None,  None,  None,  None,  0xA8,  None,  None,  None,  None,  None,  None,  None,  None],
    'TSX': [None,  None,  None,  None,  0xBA,  None,  None,  None,  None,  None,  None,  None,  None],
    'TXA': [None,  None,  None,  None,  0x8A,  None,  None,  None,  None,  None,  None,  None,  None],
    'TXS': [None,  None,  None,  None,  0x9A,  None,  None,  None,  None,  None,  None,  None,  None],
    'TYA': [None,  None,  None,  None,  0x98,  None,  None,  None,  None,  None,  None,  None,  None],
#MNEMONIC: [ #  ,   a  ,   zp ,   Acc,   Imp, ($,X), ($),Y,  zp,X,   a,X,   a,Y,   Rel,   ($),  zp,Y]
}
