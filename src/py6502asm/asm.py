"""
6502 Assembler definitions and functions
"""
from ast import literal_eval
import re

# TODO:
#   * [HIGH IMPORTANCE] TESTING!!
#   * _parse_numbers should be looked at again because it is not checking for trailing numbers (should it?)
#   * _parse_numbers should also handle string literals??
#   * Directives (not tokenized/implemented) (except .MOD)
#   * Put .MOD somewhere else
#   * Break compile functions down into smaller sub-functions
#   * More meaningful Exception classes. Not everything will be syntax. Also move error correction
#     tips somewhere else and not inside the exception itself
#   * Add clean state function

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

class IllegalOperandError(Exception):
    """
    Illegal operand/addressing mode was provided to an opcode
    """

class Assembler:
    """
    Class definition for the 6502 assembler
    """
    def __init__(self) -> None:
        self._code_bytes: dict[int, list[int]] = {} # {offset1: [bytes], offset2: [bytes], ...}
        self._current_offset: int = 0
        self._labels: dict[str, int] = {} # {label: absolute address}
        self._labels_from_prev_pass: dict[str, int] = {} # {label: absolute address}
        self._symbols: dict[str, (int, str)] = {} # {symbol: expression}
        self._errors: list[tuple[int, str]] = []

        # Uncompiled token tuple: (address_offset, code_index, opcode_str, operand_str)
        self._uncompiled_tokens: list[tuple[int, int, str, str]] = []

    def _is_hex(self, hex_string: str) -> bool:
        return bool(re.fullmatch(r'[0-9a-fA-F]+', hex_string))

    def _parse_hex(self, hex_str: str) -> int:
        if self._is_hex(hex_str):
            return literal_eval(f'0x{hex_str}')

        raise AssemblySyntaxError(f'Invalid hexadecimal value: {hex_str}')

    def _is_bin(self, bin_string: str) -> bool:
        return bool(re.fullmatch(r'[01]+', bin_string))

    def _is_dec(self, dec_string: str) -> bool:
        return bool(re.fullmatch(r'[0-9]+', dec_string))
    
    def _parse_char(self, char: str) -> int:
        if not char[1].isascii():
            raise AssemblySyntaxError(f'Invalid ascii character: {char[1]}')

        return ord(char[1])

    def _parse_bin(self, bin_str: str) -> int:
        if bin_str[0] == '%':
            if self._is_bin(bin_str[1:]):
                return literal_eval(f'0b{bin_str[1:]}')

            raise AssemblySyntaxError(f'Invalid binary value: {bin_str[1:]} -- '
                                 '(TIP: Use ".MOD" for the Modulo % operation)')

        if self._is_bin(bin_str[2:]):
            return literal_eval(f'0b{bin_str[2:]}')

        raise AssemblySyntaxError(f'Invalid binary value: {bin_str[2:]}')

    def _parse_numbers(self, asm_string: str) -> str:
        # We purposefully capture incorrect values

        # 0x00FF type
        asm_string = re.sub(
            r'(?<![a-zA-Z0-9])0x[a-zA-Z0-9]+',
            lambda x: str(self._parse_hex(x.group()[2:])),
            asm_string
        )

        # $00FF type
        asm_string = re.sub(
            r'(?<![a-zA-Z0-9])\$[a-zA-Z0-9]+',
            lambda x: str(self._parse_hex(x.group()[1:])),
            asm_string
        )

        # 0b1001 type or %1001 type
        asm_string = re.sub(
            r'(?<![a-zA-Z0-9])((%)|(0b))[a-zA-Z0-9]+',
            lambda x: str(self._parse_bin(x.group())),
            asm_string
        )

        # 'c' type
        asm_string = re.sub(
            r"(?<![a-zA-Z0-9'])'.'",
            lambda x: str(self._parse_char(x.group())),
            asm_string
        )

        # If there are still some straggling $ or % symbols
        if asm_string.count('$'):
            raise AssemblySyntaxError(
                '$ symbols should be immediately followed by a hexadecimal value '
                'and not be preceded by other alpha-numeric characters'
            )
        if asm_string.count('%'):
            raise AssemblySyntaxError('% symbols should be immediately followed by a binary value '
                                 'and not be preceded by other alpha-numeric characters\n'
                                 '(TIP: Use ".MOD" for the Modulo % operation)')

        return asm_string

    def _process_symbol(self, symbol_name: str, expression: str) -> None:
        symbol_name = symbol_name.strip()
        expression = expression.strip()

        if not expression or re.findall(r'[=:]+', expression):
            raise AssemblySyntaxError(
                'Invalid symbol declaration -- '
                'Symbol declarations should follow "SYMBOL = EXPRESSION"'
            )

        if symbol_name.count(':'):
            raise AssemblySyntaxError(
                'Labels cannot be assigned to symbol declarations'
            )

        # Check validity of symbol name
        # Leading underscores should not fail the test
        first_is_alpha = symbol_name.strip('_')[0].isalpha()
        if not (first_is_alpha and re.fullmatch(r'([A-Z_]+[0-9]*)+', symbol_name)):
            raise AssemblySyntaxError(
                f'Invalid symbol name: {symbol_name} -- '
                'Symbol names should only use alpha-numeric characters and underscores, and the '
                'first non-underscore character should be alphabetic'
            )

        if symbol_name in self._labels or symbol_name in self._symbols:
            raise AssemblySyntaxError(f'{symbol_name} already previously defined')

        if symbol_name in INSTRUCTION_MAP:
            raise AssemblySyntaxError(f'Cannot use opcode {symbol_name} as a symbol name')

        value = self._get_value(expression)

        self._symbols[symbol_name] = value

    def _process_label(self, label_token: str) -> None:
        # Is a valid label name
        # Leading underscores should not fail the test
        first_is_alpha = label_token.strip('_')[0].isalpha()
        if not (first_is_alpha and re.fullmatch(r'([A-Z_]+[0-9]*)+', label_token)):
            raise AssemblySyntaxError(
                f'Invalid label: {label_token} -- '
                'Labels should only use alpha-numeric characters and underscores, and should be '
                'followed with a colon. The first non-underscore character should be alphabetic.'
            )

        if label_token in self._labels or label_token in self._symbols:
            raise AssemblySyntaxError(f'{label_token} already previously defined')

        if label_token in INSTRUCTION_MAP:
            raise AssemblySyntaxError(f'Cannot use opcode {label_token} as a label name')

        self._labels[label_token] = self._get_current_program_counter()

    def _process_string_literal(self, string_literal: str) -> list[int]:
        string_literal = string_literal[1:-1] # Remove quotes

        if not string_literal.isascii():
            raise AssemblySyntaxError('String literals should only contain ASCII characters')

        return list(string_literal.encode().decode('unicode_escape').encode())

    def _process_directive(self, directive: str, following_str: str) -> None | list[str]:
        if directive == '.ORG':
            operand_str = self._parse_numbers(following_str)
            if not self._is_dec(operand_str):
                raise AssemblySyntaxError('.ORG directive only accepts number literal operands')
            offset = int(operand_str)

            if self._current_offset > offset:
                raise AssemblySyntaxError(
                    f'Attempting to rewind program counter offset from ${self._current_offset:04X}'
                    f' back to ${offset:04X}'
                )

            self._current_offset = offset
            self._add_bytes_to_code([]) # Important to have this initialized
            return

        if directive in ('.WORD', '.ADDR'):
            following_str = following_str.upper()
            operand_str = self._parse_numbers((''.join(following_str.split(';')[:1])).strip())
            unknown_names = set()
            for word in operand_str.split(','):
                word_value = self._get_value(word)
                if isinstance(word_value, int) and 0 <= word_value <= 0xffff:
                    self._add_bytes_to_code([word_value & 0xff, word_value >> 8])
                elif isinstance(word_value, int):
                    raise AssemblySyntaxError(f'{word} value not a positive 16-bit number')
                else:
                    # Reserve space and return unknown/illegal symbol/label names
                    self._add_bytes_to_code([0,0])
                    unknown_names.update(re.findall(
                        r'[0-9]*([A-Z_]+[0-9]*)+',
                        word
                    ))
            return list(unknown_names)

        if directive in ['.BYTE', '.BYT']:
            operand_str = self._parse_numbers((''.join(following_str.split(';')[:1])).strip())

            # First reduce string literals to decimal values
            while (match := re.search(r'"(?:\\.|[^"\\])*"', operand_str)):
                string_bytes = self._process_string_literal(match.group())
                bytes_as_string = ','.join([f'{byte}' for byte in string_bytes]) + ','
                operand_str = operand_str.replace(match.group(), bytes_as_string, 1)

            # Then reduce all other expressions to decimal values
            operand_str = self._parse_numbers(operand_str)

            # Then remove whitespaces
            operand_str = re.sub(r'[\s]+', '', operand_str).upper()

            for byte in operand_str.split(','):
                if not byte:
                    continue

                byte_value = self._get_value(byte)
                if isinstance(byte_value, int) and -128 <= byte_value <= 0xff:
                    self._add_bytes_to_code([byte_value & 0xff])
                elif isinstance(byte_value, int):
                    raise AssemblySyntaxError('Non-byte values provided.')
                else:
                    raise AssemblySyntaxError('.BYTE | .BYT only accepts constant operands')
            return

        if directive == '.ASCIIZ':
            operand_str = ''.join(following_str.split(';')[:1]).strip()

            # Ensure operand is a string literal or a comma-separated list of string literals
            if not re.match(r'^"(?:\\.|[^"\\])*"([\s]*,[\s]*"(?:\\.|[^"\\])*")*$', operand_str):
                raise AssemblySyntaxError(
                    '.ASCIIZ directive only accepts comma-separated string literal operands'
                )

            string_bytes = []
            for match in re.finditer(r'"(?:\\.|[^"\\])*"', operand_str):
                string_bytes.extend(self._process_string_literal(match.group()))
            self._add_bytes_to_code(string_bytes + [0])
            return

        raise AssemblySyntaxError(f'Unrecognized directive: {directive}')

    def _get_current_program_counter(self):
        return len(self._code_bytes.get(self._current_offset, [])) + self._current_offset

    def _test_bitwise_validity(self, value1: int, value2: int) -> None:
        if not (-128 <= value1 <= 255 and -128 <= value2 <= 255):
            raise AssemblySyntaxError('Bitwise OR/XOR/AND/NOT only operate on 8-bit values')

    def _eval_arithmetic(self, arith_string: str) -> str | int:
        """
        Using assembly operator precedence as defined in ca65's manual:
        https://cc65.github.io/doc/ca65.html#ss4.1
        EXCEPT: Shift left/right takes precedence over ^,&,.MOD,/,*
        """

        # There should be no syntax errors here. If there are, the regexes are wrong.

        # Unary bitwise not
        # First test all the expressions, and then evaluate the values
        unot_regex = r'~[-+]?[0-9]+'
        for match in re.findall(unot_regex, arith_string):
            self._test_bitwise_validity(int(match[1:]), 0)
        arith_string = re.sub(
            unot_regex,
            lambda x: str((int(x.group()[1:]) & 0xff) ^ 0xff),
            arith_string
        )

        # Unary low-byte
        # First test all the expressions, and then evaluate the values
        ulow_regex = r'(?<!<)<[-+]?[0-9]+'
        for match in re.findall(ulow_regex, arith_string):
            value = int(match[1:])
            if not 0 <= value <= 0xffff:
                raise AssemblySyntaxError(
                    'Unary low-byte can only be obtained from positive 16-bit numbers'
                )
        arith_string = re.sub(
            ulow_regex,
            lambda x: str(int(x.group()[1:]) & 0xff),
            arith_string
        )

        # Unary high-byte
        # First test all the expressions, and then evaluate the values
        uhigh_regex = r'(?<!>)>[-+]?[0-9]+'
        for match in re.findall(uhigh_regex, arith_string):
            value = int(match[1:])
            if not 0 <= value <= 0xffff:
                raise AssemblySyntaxError(
                    'Unary low-byte can only be obtained from positive 16-bit numbers'
                )
        arith_string = re.sub(
            uhigh_regex,
            lambda x: str(int(x.group()[1:]) >> 8),
            arith_string
        )

        # Bitwise shift-left, Bitwise shift-right
        # First test for negative numbers then evaluate from left to right
        if re.search(r'((<<)|(>>))-[0-9]+', arith_string):
            raise AssemblySyntaxError('Bitwise shifting with a negative number')
        shift_regex = r'(?<![0-9])[-+]?[0-9]+((<<)|(>>))[+]?[0-9]+'
        while (match := re.search(shift_regex, arith_string)):
            op = '<<' if match.group().count('<<') else '>>'
            value1, value2 = [int(val) for val in match.group().split(op)]
            if not 0 <= value1 <= 0xffff:
                raise AssemblySyntaxError(
                    'Bitwise shifts only operate on positive 16-bit numbers'
                )
            if op == '<<':
                result = (value1 << value2) & 0xffff
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
            value1, value2 = [int(val) for val in match.group().split(op)]
            if op == '%':
                result = value1 % value2
            elif op == '/':
                result = value1 // value2
            elif op == '*':
                result = value1 * value2
            elif op == '&':
                self._test_bitwise_validity(value1, value2)
                result = value1 & value2
            else: # XOR^
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
            value1 = int(match.group()[:op_match.span()[0]])
            value2 = int(match.group()[op_match.span()[1]:])
            if op == '+':
                result = value1 + value2
            elif op == '-':
                result = value1 - value2
            else: # OR|
                self._test_bitwise_validity(value1, value2)
                result = value1 | value2
            arith_string = re.sub(
                addsubor_regex,
                str(result),
                arith_string,
                count=1
            )

        return int(arith_string)

    def _get_value(self, value_string: str) -> str | int:
        # value_string should not contain any uppercase characters at this point

        # Substitute any named identifiers with their values
        # If a symbol is defined by other symbols, no change is made
        # Might contain illegal identifier names, so this should be handled later
        for named in set(re.findall(r'[A-Z0-9_]+', value_string)):
            if named in self._symbols and isinstance(self._symbols[named], int):
                value_string = value_string.replace(
                    named,
                    str(self._symbols[named])
                )
            elif named in self._labels: # First check current labels
                value_string = value_string.replace(
                    named,
                    str(self._labels[named])
                )
            elif named in self._labels_from_prev_pass: # Then check labels from previous pass
                value_string = value_string.replace(
                    named,
                    str(self._labels_from_prev_pass[named])
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

        # If there are no more symbol/label names... then it wasn't a properly formed expression
        if not re.search(r'[A-Z]', value_string):
            raise AssemblySyntaxError('Syntax error in operand')

        return value_string

    def _add_bytes_to_code(self, byte_list: list[int]) -> None:
        self._code_bytes.setdefault(self._current_offset, []).extend(byte_list)

    def _compile_opcode(self, opcode: str, operand: str) -> list[str]:
        """
        Will attempt to compile to bytes if operand can be evaluated.
        Otherwise, will reserve an estimated amount of space in code bytes
        
        Returns True if operand was successfully computed, and False otherwise
        """
        operand = re.sub(r'[\s]+', '', operand) # Remove whitespace
        operand_value = None
        opcode_index = None

        ##
        # Test for each addressing mode
        ##
        # An opcode with implied adressing mode or accumulator adressing mode was entered
        if not operand:
            opcode_index = 3 if opcode in ('ASL', 'ROL', 'LSR', 'ROR') else 4
            operand_bytes = [] if opcode != 'BRK' else [0]

        # Immediate "#"
        elif operand.startswith('#'):
            operand_value = self._get_value(operand[1:])
            if isinstance(operand_value, int):
                if not -128 <= operand_value <= 255:
                    raise IllegalOperandError(
                        f'Immediate value 8-bit overflow: #${operand_value:X}'
                    )
                operand_bytes = [operand_value & 0xff]
            else:
                operand_bytes = [0]
            opcode_index = 0

        # Indexed Indirect "(zp,X)"
        elif (match := re.search(r'(?<=^\().+(?=,X\)$)', operand)):
            operand_value = self._get_value(match.group())
            if isinstance(operand_value, int):
                if not -128 <= operand_value <= 255:
                    raise IllegalOperandError(
                        f'Zero-page address out of range: (${operand_value:X},X)'
                    )
                operand_bytes = [operand_value & 0xff]
            else:
                operand_bytes = [0]
            opcode_index = 5

        # Indirect Indexed "(zp),Y"
        elif (match := re.search(r'(?<=^\().+(?=\),Y$)', operand)):
            operand_value = self._get_value(match.group())
            if isinstance(operand_value, int):
                if not -128 <= operand_value <= 255:
                    raise IllegalOperandError(
                        f'Zero-page address out of range: (${operand_value:02X}),Y'
                    )
                operand_bytes = [operand_value & 0xff]
            else:
                operand_bytes = [0]
            opcode_index = 6

        # Absolute Indirect "(a)"
        elif (match := re.search(r'(?<=^\().+(?=\)$)', operand)):
            operand_value = self._get_value(match.group())
            if isinstance(operand_value, int):
                if not -128 <= operand_value <= 0xffff:
                    raise IllegalOperandError(f'Address out of range: (${operand_value:04X})')
                if operand_value < 0:
                    operand_value &= 0xff
                operand_bytes = [operand_value & 0xff, operand_value >> 8]
            else:
                operand_bytes = [0, 0]
            opcode_index = 11

        # Indexed Zero-page "zp,X" "zp,Y"
        # Indexed Absolute   "a,X"  "a,Y"
        elif re.search(r'.+,[XY]$', operand):
            operand_value = self._get_value(operand[:-2])
            if isinstance(operand_value, int):
                if not -128 <= operand_value <= 0xffff:
                    raise IllegalOperandError(
                        f'Address out of range: ${operand_value:02X}{operand[-2:]}'
                    )
                if not -128 <= operand_value <= 0xff: # Absolute
                    opcode_index = 8 if operand[-1] == 'X' else 9
                    operand_bytes = [operand_value & 0xff, operand_value >> 8]
                else: # Zero-page
                    opcode_index = 7 if operand[-1] == 'X' else 12
                    operand_bytes = [operand_value & 0xff]
                    if INSTRUCTION_MAP[opcode][opcode_index] is None:
                        opcode_index = 8 if operand[-1] == 'X' else 9
                        operand_bytes.append(0)
            else:
                # Determine what the maximum needed bytes would be for OPCODE
                opcode_index = 8 if operand[-1] == 'X' else 9
                if INSTRUCTION_MAP[opcode][opcode_index] is None:
                    opcode_index = 7 if operand[-1] == 'X' else 12
                    operand_bytes = [0]
                else:
                    operand_bytes = [0, 0]


        # Absolute "a"
        # Zero-page "zp"
        # Relative "Rel"
        else:
            operand_value = self._get_value(operand)

            if opcode in ('BPL', 'BMI', 'BVC', 'BVS', 'BCC', 'BCS', 'BNE', 'BEQ'):
                if isinstance(operand_value, int):
                    if not 0 <= operand_value <= 0xffff:
                        raise IllegalOperandError(
                            f'Illegal branch jump location: ${operand_value}'
                        )
                    jump_size = operand_value - (self._get_current_program_counter() + 2)
                    if not -128 <= jump_size <= 127:
                        raise IllegalOperandError(
                            f'Branch jump location out of [-128, 127] range: ${operand_value:02X}'
                            f' -- Reference address is ${self._get_current_program_counter()+2:04X}'
                        )
                    operand_bytes = [jump_size & 0xff]
                else:
                    operand_bytes = [0]
                opcode_index = 10

            else:
                if isinstance(operand_value, int):
                    if not -128 <= operand_value <= 0xffff:
                        raise IllegalOperandError(
                            f'Address out of range: ${operand_value:02X}{operand[-2:]}'
                        )
                    if not -128 <= operand_value <= 0xff: # Absolute
                        opcode_index = 1
                        operand_bytes = [operand_value & 0xff, operand_value >> 8]
                    else: # Zero-page
                        opcode_index = 2
                        operand_bytes = [operand_value & 0xff]
                        if INSTRUCTION_MAP[opcode][opcode_index] is None:
                            opcode_index = 1
                            operand_bytes.append(0)
                else:
                    opcode_index = 1
                    operand_bytes = [0,0]

        opcode_hex = INSTRUCTION_MAP[opcode][opcode_index]
        if opcode_hex is None:
            raise IllegalOperandError(f'Illegal addressing mode for opcode {opcode}')

        self._add_bytes_to_code([opcode_hex] + operand_bytes)

        # Return any unknown/illegal symbol/label names
        return re.findall(
            r'[0-9]*([A-Z_]+[0-9]*)+',
            operand_value if isinstance(operand_value, str) else ''
        )

    def _compile_line(self, asm_string: str) -> None | list[str]:
        """
        "Tokenizes" a line of text and immediately attempts to compile it to bytes.

        If a line cannot be fully compiled, a list of the unknown symbol/label names is returned.

        This function should only be called with a single line of code as its argument
        """
        if asm_string.count('\n') > 1 or asm_string.find('\n') not in [-1, len(asm_string) - 1]:
            raise AssemblySyntaxError(
                'Multiple lines fed into the line compiler. Only supply single lines.'
            )

        if not asm_string.strip():
            return

        # Find comment index
        comment_index = asm_string.find(';')
        comment_index = len(asm_string) if comment_index < 0 else comment_index

        # We pass case-sensitive string in first to parse numbers to decimal
        # After parsing is complete, we will convert to uppercase
        processed_string = self._parse_numbers(asm_string[:comment_index].strip()).upper()

        # Return on empty string
        if not processed_string:
            return

        # Since we have already handled all % characters, we can now
        # replace the .MOD operator with %
        processed_string = re.sub(r'\.MOD', '%', processed_string)

        # We can also replace the @ character with the current Program Counter
        processed_string = re.sub(
            r'@',
            str(self._get_current_program_counter()),
            processed_string
        )

        string_split = processed_string.split()

        # First check if symbols are being assigned
        if '=' in processed_string and not (sum(str_spl[0] == '.' for str_spl in string_split[:2])):
            self._process_symbol(*processed_string.strip().split('=', 1))
            return


        # Test if first token is potentially a label
        if string_split[0][-1] == ':':
            label_token = string_split.pop(0)
            self._process_label(label_token[:-1])

        # Line only had a label
        if not string_split:
            return

        # Handle any possible directives
        if string_split[0][0] == '.':
            # Pass the directive and original string following the directive
            self._process_directive(
                string_split[0],
                re.search(
                    f'(?<=\\{string_split[0]}).*',
                    asm_string[:comment_index],
                    re.IGNORECASE
                ).group().strip()
            )
            return

        # Handle opcodes
        if string_split[0] in INSTRUCTION_MAP:
            return self._compile_opcode(string_split[0], ''.join(string_split[1:]))

        raise AssemblySyntaxError(f'Unrecognized statement: {' '.join(string_split)}')

    def assemble_from_string(self, asm_string: str) -> bytes:
        self._code_bytes = {}
        self._current_offset = 0
        self._labels = {}
        self._labels_from_prev_pass = {}
        self._symbols = {}
        unknowns = []

        for i, line in enumerate(asm_string.split('\n')):
            try:
                unknowns.extend(self._compile_line(line) or [])
            except AssemblySyntaxError as e:
                print(f'Error on line {i+1}: {e}')
                return bytes([])

        if unknowns:
            prev_code_bytes = {}
            while prev_code_bytes != self._code_bytes:
                prev_code_bytes = self._code_bytes
                self._labels_from_prev_pass = self._labels
                self._code_bytes = {}
                self._current_offset = 0
                self._labels = {}
                self._symbols = {}
                unknowns = []

                for line in asm_string.split('\n'):
                    unknowns.extend(self._compile_line(line) or [])

        if unknowns:
            raise AssemblySyntaxError(f'Unknown labels referenced: {unknowns}')

        code = []
        code_offsets = sorted(self._code_bytes.keys())
        for index, offset in enumerate(code_offsets):
            offset_code_len = len(self._code_bytes[offset])

            if offset + offset_code_len > 0x10000:
                raise AssemblySyntaxError('Assembled code larger than 64K')

            if index + 1 < len(code_offsets):
                next_offset = code_offsets[index + 1]
                if not offset + offset_code_len <= next_offset:
                    raise AssemblySyntaxError(
                        f'Code segment at offset ${offset:03X} (Bytes: {offset_code_len}) '
                        f'overlaps with code segment at offset {next_offset:03X}'
                    )

                # Pad code with zeros between offsets
                self._code_bytes[offset].extend([0] * (next_offset - offset - offset_code_len))

            code.extend(self._code_bytes[offset])
            print(f'${offset:04X}: Assembled {offset_code_len} bytes')

        return bytes(code)

    def assemble_from_file(self, filename: str) -> bytes:
        with open(filename, 'r', encoding='utf-8') as file_handle:
            return self.assemble_from_string(file_handle.read())

    def assemble_from_file_and_output(self, src_filename: str, dst_filename: str) -> int:
        byte_code = self.assemble_from_file(src_filename)

        if byte_code:
            with open(dst_filename, 'wb') as file_handle:
                return file_handle.write(byte_code)
        else:
            print('Assembly failed. No output file created.')
            return 0

INSTRUCTION_MAP = {
#MNEMONIC: [ #  ,   a  ,   zp ,   Acc,   Imp, ($,X), ($),Y,  zp,X,   a,X,   a,Y,   r  ,   ($),  zp,Y]
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
    # BRK is always a 2-byte instruction, but the user does not need to specify an operand.
    # However we will make provision for it having either an immediate value or no operand at all.
    'BRK': [0x00,  None,  None,  None,  0x00,  None,  None,  None,  None,  None,  None,  None,  None],
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
    'STA': [None,  0x8D,  0x85,  None,  None,  0x81,  0x91,  0x95,  0x9D,  0x99,  None,  None,  None],
    'STX': [None,  0x8E,  0x86,  None,  None,  None,  None,  None,  None,  None,  None,  None,  0x96],
    'STY': [None,  0x8C,  0x84,  None,  None,  None,  None,  0x94,  None,  None,  None,  None,  None],
    'TAX': [None,  None,  None,  None,  0xAA,  None,  None,  None,  None,  None,  None,  None,  None],
    'TAY': [None,  None,  None,  None,  0xA8,  None,  None,  None,  None,  None,  None,  None,  None],
    'TSX': [None,  None,  None,  None,  0xBA,  None,  None,  None,  None,  None,  None,  None,  None],
    'TXA': [None,  None,  None,  None,  0x8A,  None,  None,  None,  None,  None,  None,  None,  None],
    'TXS': [None,  None,  None,  None,  0x9A,  None,  None,  None,  None,  None,  None,  None,  None],
    'TYA': [None,  None,  None,  None,  0x98,  None,  None,  None,  None,  None,  None,  None,  None],
#MNEMONIC: [ #  ,   a  ,   zp ,   Acc,   Imp, ($,X), ($),Y,  zp,X,   a,X,   a,Y,   r  ,   ($),  zp,Y]
}
