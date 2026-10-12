"""Out-of-order execution with integer/address occupancy and pipelined FP units."""
from .init import Task, Result


def _ready(entry, cycle, unit):
    if entry.issue >= cycle:
        return False
    if unit == "ls":
        base = entry.operand1 if entry.op == "ld" else entry.operand2
        return base.available(cycle)
    return entry.operand1.available(cycle) and entry.operand2.available(cycle)


def _finish(machine, task, cycle):
    e = task.entry
    if e.squashed:
        return
    a, b, op = e.operand1.value, e.operand2.value, e.op
    if task.unit == "ls":
        base = a if op == "ld" else b
        address = base + e.instruction.immediate
        if not isinstance(address, int) or not 0 <= address < 256:
            e.fault = f"Invalid memory byte address {address}; expected integer in [0,255]"
            return
        e.address = address
        if op == "sd":
            machine.check_memory_violation(e, cycle)
        return
    if op in ("beq", "bne"):
        taken = a == b if op == "beq" else a != b
        offset = e.instruction.immediate
        if machine.branch_offset_mode == "bytes":
            if offset % 4:
                e.fault = "Legacy byte branch offset must be divisible by four"
                e.ready = True
                return
            offset //= 4
        target = e.pc + 1 + offset
        actual = target if taken else e.pc + 1
        e.actual_next = actual
        e.ready = True
        if not 0 <= actual <= len(machine.instructions):
            e.fault = f"Branch target outside instruction buffer: PC word {actual}"
            machine.squash_after(e.seq, len(machine.instructions), cycle, reason="branch_fault")
            return
        machine.predictor[e.pc] = taken
        machine.btb[e.pc & 7] = (e.pc, target)
        if actual != e.predicted_next:
            machine.stats["mispredictions"] += 1
            machine.squash_after(e.seq, actual, cycle)
        return
    if op in ("add", "addi", "add.d"):
        value = a + b
    elif op in ("sub", "sub.d"):
        value = a - b
    else:
        value = a * b
    machine.results.append(Result(e, value, cycle))


def exe(machine, cycle):
    # Each task advances once per cycle; newly dispatched tasks cannot be advanced twice.
    completing = sorted((t for t in machine.tasks if t.end == cycle), key=lambda t: t.entry.seq)
    for task in completing:
        if not task.entry.squashed:
            _finish(machine, task, cycle)
    machine.tasks = [t for t in machine.tasks if t.end > cycle and not t.entry.squashed]
    for unit in ("int", "fp_add", "fp_mul", "ls"):
        count = getattr(machine.config, {"int": "int_fus", "fp_add": "fp_add_fus", "fp_mul": "fp_mul_fus", "ls": "ls_fus"}[unit])
        latency = getattr(machine.config, {"int": "int_ex", "fp_add": "fp_add_ex", "fp_mul": "fp_mul_ex", "ls": "ls_ex"}[unit])
        # Unpipelined units remain occupied throughout their completion cycle.
        if unit in ("int", "ls"):
            occupied = sum(t.unit == unit and not t.entry.squashed for t in machine.tasks)
            finished_now = sum(t.unit == unit and not t.entry.squashed for t in completing)
            available = max(0, count - occupied - finished_now)
        else:
            available = count
        entries = machine.lsq if unit == "ls" else machine.rs[unit]
        candidates = sorted((e for e in entries if not e.exe and _ready(e, cycle, unit)), key=lambda e: e.seq)
        for e in candidates[:available]:
            if e.squashed:
                continue
            e.exe[:] = [cycle, cycle + latency - 1]
            task = Task(e, cycle, cycle + latency - 1, unit)
            if unit != "ls":
                machine.rs[unit].remove(e)
            if latency == 1:
                _finish(machine, task, cycle)
            else:
                machine.tasks.append(task)
