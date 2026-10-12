"""A single common data bus broadcasts one completed result per cycle."""


def wb(machine, cycle):
    eligible = [r for r in machine.results if r.completed < cycle and not r.entry.squashed]
    if not eligible:
        return
    result = min(eligible, key=lambda r: (r.completed, r.entry.seq))
    machine.results.remove(result)
    entry = result.entry
    entry.value = result.value
    entry.wb = cycle
    entry.ready = True
    # Wake operands by immutable dynamic tag. A younger WAW rename stays in the RAT.
    for waiting in machine.rob:
        for operand in (waiting.operand1, waiting.operand2):
            if operand.tag == entry.seq:
                operand.tag = None
                operand.value = result.value
                operand.ready_cycle = cycle
