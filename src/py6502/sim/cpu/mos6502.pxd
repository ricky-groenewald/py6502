"""
CYTHON MOS6502 PROCESSOR CLASS DECLARATIONS
"""
from py6502.sim.bus.component cimport Component

ctypedef int (*instruction_func)(MOS6502) except -1

cdef struct Registers:
    unsigned char OPCODE # Not a real register, but used for debugging
    unsigned short OPCODE_ADDR
    unsigned char INTERRUPT_TYPE # Not a real register, but used for debugging
                                 # 0 = None/BRK, 1 = IRQ, 2 = RESET, 3 = NMI
    unsigned char ACC
    unsigned char X
    unsigned char Y
    unsigned short PC
    unsigned char S
    unsigned char P

cdef class MOS6502:

    # Registers
    cdef Registers _registers

    # External memory bus
    cdef Component _memory_bus

    # Internal variables
    cdef unsigned char _invalid_opcode_mode  # 0 = NOP, 1 = crash
    cdef unsigned char _cycle_number
    cdef unsigned char _temp_data
    cdef unsigned short _temp_address
    cdef bint _page_cross_possible
    cdef bint _page_cross_occurred
    cdef bint _accumulator_addressing
    cdef unsigned short _arithmetic_result
    cdef signed char _branch_offset
    cdef bint _decimal_mode_was_set

    # Instruction function references
    cdef instruction_func[256][2] _instructions
    cdef instruction_func _current_instruction
    cdef instruction_func _next_instruction

    # Getters
    cdef Registers get_registers(self)

    # Setters
    cdef void set_registers(self, Registers registers)

    # Control Functions
    cdef int clock(self) except -1
    cdef void send_reset(self)
    cdef void send_irq(self)
    cdef void send_nmi(self)
    cdef int load_op_code(self) except -1
    cdef void set_memory_bus(self, Component memory_bus)
    cdef void set_invalid_opcode_mode(self, unsigned char mode)
    cdef void clear_bcd_opcodes(self)
    cdef void set_bcd_opcodes(self)

    # Addressing Modes
    cdef int absolute(self) except -1
    cdef int absolute_x(self) except -1
    cdef int absolute_y(self) except -1
    cdef int accumulator(self) except -1
    cdef int immediate(self) except -1 # Also handles relative addressing
    cdef int implied(self) except -1
    cdef int indirect(self) except -1
    cdef int indirect_x(self) except -1
    cdef int indirect_y(self) except -1
    cdef int zero_page(self) except -1
    cdef int zero_page_x(self) except -1
    cdef int zero_page_y(self) except -1

    # # Opcode functions
    cdef int ADC_SBC(self) except -1
    cdef int ADC_SBC_BCD(self) except -1
    cdef int AND(self) except -1
    cdef int ASL(self) except -1
    cdef int BCC(self) except -1
    cdef int BCS(self) except -1
    cdef int BEQ(self) except -1
    cdef int BIT(self) except -1
    cdef int BMI(self) except -1
    cdef int BNE(self) except -1
    cdef int BPL(self) except -1
    cdef int BRK(self) except -1
    cdef int BVC(self) except -1
    cdef int BVS(self) except -1
    cdef int CLC(self) except -1
    cdef int CLD(self) except -1
    cdef int CLI(self) except -1
    cdef int CLV(self) except -1
    cdef int CMP(self) except -1
    cdef int CPX(self) except -1
    cdef int CPY(self) except -1
    cdef int DEC(self) except -1
    cdef int DEX(self) except -1
    cdef int DEY(self) except -1
    cdef int EOR(self) except -1
    cdef int INC(self) except -1
    cdef int INX(self) except -1
    cdef int INY(self) except -1
    cdef int JMP(self) except -1
    cdef int JSR(self) except -1
    cdef int LDA(self) except -1
    cdef int LDX(self) except -1
    cdef int LDY(self) except -1
    cdef int LSR(self) except -1
    cdef int NOP(self) except -1
    cdef int ORA(self) except -1
    cdef int PHA(self) except -1
    cdef int PHP(self) except -1
    cdef int PLA(self) except -1
    cdef int PLP(self) except -1
    cdef int ROL(self) except -1
    cdef int ROR(self) except -1
    cdef int RTI(self) except -1
    cdef int RTS(self) except -1
    cdef int SEC(self) except -1
    cdef int SED(self) except -1
    cdef int SEI(self) except -1
    cdef int STA(self) except -1
    cdef int STX(self) except -1
    cdef int STY(self) except -1
    cdef int TAX(self) except -1
    cdef int TAY(self) except -1
    cdef int TSX(self) except -1
    cdef int TXA(self) except -1
    cdef int TXS(self) except -1
    cdef int TYA(self) except -1
