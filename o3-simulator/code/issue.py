"""In-order issue, structural hazards, source capture, and branch prediction."""
from .init import Operand, ROBEntry


def read_operand(machine, name):
    if name is None:
        return Operand()
    if name == "R0":
        return Operand(0)
    tag = machine.rat.get(name)
    if tag is not None:
        producer = machine.by_seq[tag]
        if producer.wb is not None:
            return Operand(producer.value, None, producer.wb if producer.wb is not None else -1)
        return Operand(0, tag)
    values = machine.reg_int if name[0] == "R" else machine.reg_fp
    return Operand(values[int(name[1:])])


def unit_for(op):
    if op in ("ld", "sd"):
        return "ls"
    if op in ("add.d", "sub.d"):
        return "fp_add"
    if op == "mult.d":
        return "fp_mul"
    return "int"


def issue(machine, cycle):
    if cycle < machine.fetch_resume:
        return
    for _ in range(machine.config.issue_width):
        if machine.pc == len(machine.instructions):
            break
        if not 0 <= machine.pc < len(machine.instructions):
            return  # An unresolved speculative branch may redirect this fetch.
        ins = machine.instructions[machine.pc]
        unit = unit_for(ins.op)
        capacity = getattr(machine.config, {"int": "int_rs", "fp_add": "fp_add_rs", "fp_mul": "fp_mul_rs", "ls": "lsq_size"}[unit])
        occupied = len(machine.lsq) if unit == "ls" else len(machine.rs[unit])
        if len(machine.rob) >= machine.config.rob_entries or occupied >= capacity:
            machine.stats["issue_stalls"] += 1
            break  # No younger instruction bypasses this structural hazard.
        source1 = read_operand(machine, ins.src1)
        source2 = read_operand(machine, ins.src2)
        if ins.op == "addi":
            source2 = Operand(ins.immediate)
        entry = ROBEntry(machine.next_seq, machine.pc, ins, source1, source2, cycle)
        machine.next_seq += 1
        machine.by_seq[entry.seq] = entry
        machine.rob.append(entry)
        machine.history.append(entry)
        machine.stats["issued"] += 1
        if unit == "ls":
            machine.lsq.append(entry)
        else:
            machine.rs[unit].append(entry)
        if ins.dest is not None and ins.dest != "R0":
            machine.rat[ins.dest] = entry.seq
        next_pc = machine.pc + 1
        if ins.op in ("beq", "bne"):
            btb = machine.btb[machine.pc & 7]
            if machine.predictor.get(machine.pc, False) and btb is not None and btb[0] == machine.pc:
                next_pc = btb[1]
                machine.stats["btb_hits"] += 1
            entry.predicted_next = next_pc
        machine.pc = next_pc
