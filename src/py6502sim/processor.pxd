"""
CYTHON MOS6502 PROCESSOR CLASS DECLARATIONS
"""
from .component cimport Component

ctypedef void (*instruction_func)(MOS6502)

cdef struct Registers:
    unsigned char OPCODE # Not a real register, but used for debugging
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
    cdef unsigned char _cycle_number
    cdef unsigned char _temp_data
    cdef unsigned short _temp_address
    cdef unsigned char _incoming_interrupt_flag
    cdef bint _page_cross_possible
    cdef bint _page_cross_occurred
    cdef bint _accumulator_addressing
    cdef unsigned short _arithmetic_result
    cdef signed char _branch_offset

    # Instruction function references
    cdef instruction_func[256][2] _instructions
    cdef instruction_func _current_instruction
    cdef instruction_func _next_instruction
    cdef unsigned char[16] _adc_sbc_opcodes

    # Control Functions
    cdef void clock(self)
    # cdef void send_reset(self)
    # cdef void send_irq(self)
    # cdef void send_nmi(self)
    # cdef void handle_interrupt(self)
    cdef void load_op_code(self)
    # cdef void clear_bcd_opcodes(self)
    # cdef void set_bcd_opcodes(self)

    # Addressing Modes
    cdef void absolute(self)
    cdef void absolute_x(self)
    cdef void absolute_y(self)
    cdef void accumulator(self)
    cdef void immediate(self) # Also handles relative addressing
    cdef void implied(self)
    cdef void indirect_x(self)
    cdef void indirect_y(self)
    cdef void zero_page(self)
    cdef void zero_page_x(self)
    cdef void zero_page_y(self)

    # # Opcode functions
    cdef void ADC_SBC(self)
    # cdef void ADC_SBC_BCD(self)
    cdef void AND(self)
    cdef void ASL(self)
    cdef void BCC(self)
    cdef void BCS(self)
    cdef void BEQ(self)
    cdef void BIT(self)
    cdef void BMI(self)
    cdef void BNE(self)
    cdef void BPL(self)
    # cdef void BRK(self)
    cdef void BVC(self)
    cdef void BVS(self)
    cdef void CLC(self)
    cdef void CLD(self)
    cdef void CLI(self)
    cdef void CLV(self)
    cdef void CMP(self)
    cdef void CPX(self)
    cdef void CPY(self)
    cdef void DEC(self)
    cdef void DEX(self)
    cdef void DEY(self)
    cdef void EOR(self)
    cdef void INC(self)
    cdef void INX(self)
    cdef void INY(self)
    # cdef void JMP(self)
    # cdef void JSR(self)
    cdef void LDA(self)
    cdef void LDX(self)
    cdef void LDY(self)
    cdef void LSR(self)
    cdef void NOP(self)
    # cdef void ORA(self)
    # cdef void PHA(self)
    # cdef void PHP(self)
    # cdef void PLA(self)
    # cdef void PLP(self)
    # cdef void ROL(self)
    # cdef void ROR(self)
    # cdef void RTI(self)
    # cdef void RTS(self)
    cdef void SEC(self)
    cdef void SED(self)
    cdef void SEI(self)
    # cdef void STA(self)
    # cdef void STX(self)
    # cdef void STY(self)
    # cdef void TAX(self)
    # cdef void TAY(self)
    # cdef void TSX(self)
    # cdef void TXA(self)
    # cdef void TXS(self)
    # cdef void TYA(self)

    # Getters
    cpdef Registers get_registers(self)

    # Setters
    cpdef void set_registers(self, Registers registers)
