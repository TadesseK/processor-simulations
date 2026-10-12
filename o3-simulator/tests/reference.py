"""Small sequential ISA interpreter, independent of the simulator and its parser.

This checks architectural behavior, not the timing model. Instructions are read
directly from the input text so decoder mistakes are not shared with the oracle.
"""

from dataclasses import dataclass
import re
from pathlib import Path


@dataclass
class ReferenceResult:
    reg_int: list
    reg_fp: list
    memory: list
    committed_pcs: list


OPS = {"add", "sub", "addi", "add.d", "sub.d", "mult.d", "ld", "sd", "beq", "bne"}


def interpret(path, branch_offset_mode="words", max_instructions=10000):
    """Execute the documented ISA in program order, with byte-addressed memory."""
    integers = [0] * 32
    floats = [0.0] * 32
    memory = [0.0] * 256
    program = []
    for raw in Path(path).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        first = line.split()[0].lower()
        if first in OPS:
            program.append(re.split(r"[\s,]+", line.lower()))
            continue
        for name, number in re.findall(r"\b([rf]\d+)\s*=\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)", line, re.I):
            name = name.lower()
            index = int(name[1:])
            if name.startswith("r"):
                integers[index] = int(float(number))
            else:
                floats[index] = float(number)
        for address, number in re.findall(r"mem\[(\d+)\]\s*=\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)", line, re.I):
            memory[int(address)] = float(number)
    integers[0] = 0

    def read(register):
        bank = floats if register.startswith("f") else integers
        return bank[int(register[1:])]

    def write(register, value):
        index = int(register[1:])
        if register.startswith("f"):
            floats[index] = value
        elif index != 0:
            integers[index] = value

    def address(expression):
        match = re.fullmatch(r"([-+]?\d+)\((r\d+)\)", expression)
        if not match:
            raise ValueError("Invalid reference memory operand: " + expression)
        effective = read(match.group(2)) + int(match.group(1))
        if not isinstance(effective, int) or effective < 0 or effective > 255:
            raise ValueError("Invalid reference memory address: " + str(effective))
        return effective

    pc = 0
    committed = []
    while 0 <= pc < len(program):
        if len(committed) >= max_instructions:
            raise RuntimeError("Reference program did not terminate")
        parts = program[pc]
        op = parts[0]
        committed.append(pc * 4)
        next_pc = pc + 1
        if op in {"add", "add.d", "sub", "sub.d", "mult.d"}:
            left, right = read(parts[2]), read(parts[3])
            if op in {"add", "add.d"}:
                value = left + right
            elif op in {"sub", "sub.d"}:
                value = left - right
            else:
                value = left * right
            write(parts[1], value)
        elif op == "addi":
            write(parts[1], read(parts[2]) + int(parts[3]))
        elif op == "ld":
            write(parts[1], memory[address(parts[2])])
        elif op == "sd":
            memory[address(parts[2])] = read(parts[1])
        elif op in {"beq", "bne"}:
            equal = read(parts[1]) == read(parts[2])
            taken = equal if op == "beq" else not equal
            if taken:
                displacement = int(parts[3])
                if branch_offset_mode == "bytes":
                    if displacement % 4:
                        raise ValueError("Legacy branch displacement must be divisible by four")
                    displacement //= 4
                elif branch_offset_mode != "words":
                    raise ValueError("Unknown branch offset mode")
                next_pc += displacement
        pc = next_pc
        integers[0] = 0
    return ReferenceResult(integers, floats, memory, committed)
