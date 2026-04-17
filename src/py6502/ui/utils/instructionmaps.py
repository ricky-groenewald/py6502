"""6502 mnemonic → opcode-per-addressing-mode lookup table.

This is the source-of-truth for opcode disassembly in the debug panel.
``windows/debug.py`` flips it into an opcode → "MNEMONIC mode" dict at
build time via ``_build_opcode_disasm`` so every refresh of the
register panel is a single dict lookup.

Column order (matches ADDRESSING_MODES in windows/debug.py):
    immediate, absolute, zero-page, accumulator, implied,
    (indirect,X), (indirect),Y, zero-page,X, absolute,X, absolute,Y,
    relative, (indirect), zero-page,Y.

``None`` means "this mnemonic has no encoding in that addressing mode".
"""
INSTRUCTION_MAP_6502 = {
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
    # BRK is always 2 bytes on the wire, but the operand byte is
    # ignored — list it under both "immediate" and "implied" so the
    # disassembler can render either spelling without lying.
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