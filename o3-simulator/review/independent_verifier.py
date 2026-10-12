"""Independent architectural review, reproducible from the submission root.

Run: python review/independent_verifier.py

The oracle below executes assembly strings sequentially and does not use the
simulator's instruction parser. Timing checks in the primary unittest suite
remain separate from this architectural comparison.
"""
from pathlib import Path
import math
import random
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from code.init import Config, parse_instruction
from code.simulator import Simulator


def reference(program, integers, floats, memory):
    integers, floats, memory = list(integers), list(floats), list(memory)
    committed_pcs = []
    pc = 0

    def read(register):
        return (integers if register[0] == "R" else floats)[int(register[1:])]

    while pc < len(program):
        parts = program[pc].replace(",", " ").split()
        op = parts[0].lower()
        next_pc = pc + 1
        committed_pcs.append(pc)
        if op in ("ld", "sd"):
            operand = re.fullmatch(r"([-+]?\d+)\((R\d+)\)", parts[2])
            address = int(operand[1]) + read(operand[2])
            if op == "ld":
                floats[int(parts[1][1:])] = memory[address]
            else:
                memory[address] = read(parts[1])
        elif op in ("beq", "bne"):
            equal = read(parts[1]) == read(parts[2])
            if equal == (op == "beq"):
                next_pc += int(parts[3])
        else:
            left = read(parts[2])
            right = int(parts[3]) if op == "addi" else read(parts[3])
            if op in ("add", "add.d", "addi"):
                value = left + right
            elif op in ("sub", "sub.d"):
                value = left - right
            else:
                value = left * right
            bank = integers if parts[1][0] == "R" else floats
            if parts[1] != "R0":
                bank[int(parts[1][1:])] = value
        pc = next_pc
        integers[0] = 0
    return integers, floats, memory, committed_pcs


def compare(expected, result, context):
    actual = (result.reg_int, result.reg_fp, result.memory,
              [entry.pc for entry in result.history if entry.commit is not None])
    for bank, (want, got) in enumerate(zip(expected, actual)):
        if bank == 3:
            correct = want == got
        else:
            correct = all(a == b or math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
                          for a, b in zip(want, got))
        assert correct, f"{context}: bank {bank}, expected {want}, got {got}"


def randomized_checks():
    rng = random.Random(92731)
    runs = 0
    for case in range(250):
        integers = [0] * 32
        integers[1], integers[2], integers[3] = 4, 8, 12
        floats = [float(rng.randrange(-3, 4)) for _ in range(32)]
        memory = [float(rng.randrange(-5, 6)) for _ in range(256)]
        program = []
        for position in range(35):
            op = rng.choice(["add", "sub", "addi", "add.d", "sub.d", "mult.d",
                             "ld", "sd", "beq", "bne", "address"])
            if op == "address":
                program.append(f"Addi R10, R0, {rng.choice([0, 4, 8, 12])}")
            elif op in ("ld", "sd"):
                program.append(f"{op} F{rng.randrange(8)}, 0(R{rng.choice([0, 1, 2, 3, 10])})")
            elif op in ("beq", "bne"):
                program.append(f"{op} R{rng.randrange(11, 20)}, R{rng.randrange(11, 20)}, "
                               f"{rng.randrange(0, min(4, 35-position))}")
            elif op in ("add", "sub"):
                program.append(f"{op} R{rng.choice([0]+list(range(11, 20)))}, "
                               f"R{rng.randrange(11, 20)}, R{rng.randrange(11, 20)}")
            elif op == "addi":
                program.append(f"Addi R{rng.randrange(11, 20)}, R{rng.randrange(11, 20)}, "
                               f"{rng.randrange(-9, 10)}")
            else:
                program.append(f"{op} F{rng.randrange(8)}, F{rng.randrange(8)}, F{rng.randrange(8)}")
        expected = reference(program, integers, floats, memory)
        for width in range(1, 5):
            config = Config(
                issue_width=width, int_rs=rng.randrange(1, 7),
                fp_add_rs=rng.randrange(1, 7), fp_mul_rs=rng.randrange(1, 7),
                lsq_size=rng.randrange(1, 7), rob_entries=rng.randrange(1, 20),
                int_fus=rng.randrange(1, 4), fp_add_fus=rng.randrange(1, 4),
                fp_mul_fus=rng.randrange(1, 4), ls_fus=rng.randrange(1, 4),
                int_ex=rng.randrange(1, 6), fp_add_ex=rng.randrange(1, 6),
                fp_mul_ex=rng.randrange(1, 9), ls_ex=rng.randrange(1, 4),
                mem_cycles=rng.randrange(1, 7))
            machine = Simulator(config, [parse_instruction(line) for line in program],
                                integers, floats, memory)
            result = machine.run()
            compare(expected, result, f"case {case}, width {width}, config {vars(config)}")
            runs += 1
    print(f"PASS: {runs} randomized architectural checks; seed 92731; 250 programs x widths 1-4")


def directed_checks():
    for offset, expected, replay in ((4, 9, False), (0, 7, True)):
        config = Config(int_ex=8, fp_mul_ex=20, issue_width=4, lsq_size=4, int_rs=4)
        program = ["Mult.d F31, F0, F0", "Sd F1, 0(R0)",
                   f"Addi R1, R0, {offset}", "Sd F2, 0(R1)", "Ld F3, 0(R0)"]
        floats = [0.0] * 32
        floats[1], floats[2] = 9, 7
        memory = [0.0] * 256
        memory[0] = 1
        machine = Simulator(config, [parse_instruction(line) for line in program],
                            reg_fp=floats, memory=memory)
        result = machine.run()
        assert result.reg_fp[3] == expected
        assert (result.stats["replays"] > 0) == replay
        assert result.stats["forwarded_loads"] > 0
        name = "late alias" if replay else "late nonalias"
        print(f"PASS: provisional newest-known-store forwarding with {name}; "
              f"F3={result.reg_fp[3]}; replays={result.stats['replays']}")

    fault_programs = [
        ("load and later-issued dependent", 1, 1,
         ["Addi R1, R0, 1", "Bne R1, R0, 3", "Ld F1, -1(R0)",
          "Add.d F2, F1, F3", "Addi R7, R0, 99", "Addi R8, R0, 7"]),
        ("branch target", 4, 2,
         ["Addi R1, R0, 1", "Bne R1, R0, 3", "Beq R0, R0, 99",
          "Add.d F2, F1, F3", "Addi R7, R0, 99", "Addi R8, R0, 7"]),
    ]
    for name, width, int_fus, program in fault_programs:
        config = Config(issue_width=width, int_ex=8, int_fus=int_fus,
                        int_rs=4, lsq_size=4, fp_add_rs=4)
        machine = Simulator(config, [parse_instruction(line) for line in program])
        result = machine.run()
        assert result.reg_int[7] == 0 and result.reg_int[8] == 7
        assert any(entry.squashed and entry.fault for entry in result.history)
        branch_event = next(event for event in machine.events if event["trigger_seq"] == 1)
        correct = [entry for entry in result.history if entry.pc == 5 and not entry.squashed]
        assert correct[0].issue == branch_event["cycle"] + 2
        print(f"PASS: speculative invalid {name} discarded; correct fetch resumes at n+2")


if __name__ == "__main__":
    randomized_checks()
    directed_checks()
