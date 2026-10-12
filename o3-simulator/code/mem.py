"""Load memory access, newest older-store forwarding, and speculative bypass."""
from .init import Result


def finish_load(machine, entry, value, cycle):
    machine.results.append(Result(entry, value, cycle))
    if entry in machine.lsq:
        machine.lsq.remove(entry)


def mem(machine, cycle):
    active = machine.memory_task
    if active is not None and active[0].op == "ld" and active[2] == cycle:
        e, value, _ = active
        if not e.squashed:
            finish_load(machine, e, value, cycle)
        machine.memory_task = None
        machine.memory_free_after = cycle
    # Forwarding does not occupy the external memory port. At most one MEM start
    # is selected here per cycle, and ordinary memory access remains nonpipelined.
    for e in sorted(machine.lsq, key=lambda e: e.seq):
        if e.op != "ld" or not e.exe or e.exe[-1] >= cycle or e.mem or e.fault:
            continue
        older = [s for s in machine.lsq if s.op == "sd" and s.seq < e.seq]
        matching = [s for s in older if s.address == e.address]
        source = max(matching, key=lambda s: s.seq) if matching else None
        # Forward the newest known match provisionally. A later-resolved older
        # store can still supersede this value; alias recovery will replay it.
        if source is not None:
            if not source.operand1.available(cycle):
                continue
            e.mem[:] = [cycle, cycle]
            e.forwarded_from = source.seq
            machine.stats["forwarded_loads"] += 1
            finish_load(machine, e, source.operand1.value, cycle)
            break
        if source is None:
            if machine.memory_task is not None or cycle <= machine.memory_free_after:
                continue
            end = cycle + machine.config.mem_cycles - 1
            e.mem[:] = [cycle, end]
            value = machine.memory[e.address]
            if end == cycle:
                finish_load(machine, e, value, cycle)
                machine.memory_free_after = cycle
            else:
                machine.memory_task = (e, value, end)
            break
