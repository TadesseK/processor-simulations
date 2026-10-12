"""In-order retirement and store memory writes at the commit boundary."""


def commit(machine, cycle):
    if not machine.rob:
        return
    e = machine.rob[0]
    if e.fault and e.exe and e.exe[-1] < cycle:
        raise ValueError(f"Instruction {e.pc}: {e.fault}")
    if e.op == "sd":
        if not e.exe or e.exe[-1] >= cycle or not e.operand1.available(cycle):
            return
        if not e.mem:
            if machine.memory_task is not None or cycle <= machine.memory_free_after:
                return
            end = cycle + machine.config.mem_cycles - 1
            e.mem[:] = [cycle, end]
            machine.memory_task = (e, e.operand1.value, end)
        if e.mem[-1] != cycle:
            return
        machine.memory[e.address] = e.operand1.value
        machine.memory_task = None
        machine.memory_free_after = cycle
        machine.lsq.remove(e)
    elif e.op in ("beq", "bne"):
        if not e.ready or not e.exe or e.exe[-1] >= cycle:
            return
    else:
        if e.wb is None or e.wb >= cycle:
            return
        if e.dest is not None and e.dest != "R0":
            values = machine.reg_int if e.dest[0] == "R" else machine.reg_fp
            values[int(e.dest[1:])] = e.value
        if machine.rat.get(e.dest) == e.seq:
            del machine.rat[e.dest]
    e.commit = cycle
    machine.rob.pop(0)
    machine.stats["committed"] += 1
