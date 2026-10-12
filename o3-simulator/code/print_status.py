"""Human-readable instruction status and architectural state output."""


def _interval(value):
    if not value:
        return "-"
    return str(value[0]) if value[0] == value[-1] else f"{value[0]}-{value[-1]}"


def format_result(result):
    lines = ["FINAL INSTRUCTION STATUS", "ID   PC   Instruction                    ISSUE   EX        MEM       WB    COMMIT   STATUS"]
    for e in result.history:
        lines.append(f"{e.seq:<4} {e.pc * 4:<4} {e.instruction.text:<30} {e.issue:<7} {_interval(e.exe):<9} {_interval(e.mem):<9} {str(e.wb) if e.wb is not None else '-':<5} {str(e.commit) if e.commit is not None else '-':<8} {'SQUASHED' if e.squashed else 'COMMITTED'}")
    lines.extend(["", "REGISTER VALUES"])
    for label, values in (("R", result.reg_int), ("F", result.reg_fp)):
        for start in range(0, 32, 8):
            lines.append(" ".join(f"{label}{i}={values[i]:g}" for i in range(start, start + 8)))
    lines.extend(["", "NON-ZERO MEMORY VALUES", "Address   Value"])
    cells = [(i, value) for i, value in enumerate(result.memory) if value != 0]
    lines.extend(f"{address:<9} {value:g}" for address, value in cells)
    if not cells:
        lines.append("(none)")
    lines.extend(["", f"TOTAL CYCLES: {result.cycles}", "COUNTERS: " + ", ".join(f"{k}={v}" for k, v in result.stats.items())])
    return "\n".join(lines) + "\n"


def result_dict(result):
    return {"cycles": result.cycles, "stats": result.stats,
            "reg_int": result.reg_int, "reg_fp": result.reg_fp,
            "memory": {str(i): v for i, v in enumerate(result.memory) if v != 0},
            "history": [{"seq": e.seq, "pc": e.pc * 4, "pc_word": e.pc,
                         "instruction": e.instruction.text, "op": e.op,
                         "issue": e.issue, "exe": e.exe, "mem": e.mem,
                         "wb": e.wb, "commit": e.commit, "squashed": e.squashed,
                         "squash_cycle": e.squash_cycle,
                         "value": e.value, "address": e.address,
                         "forwarded_from": e.forwarded_from}
                        for e in result.history]}
