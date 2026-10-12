"""Reproduce all finite fixture results and check an independent ISA oracle."""
import csv
import hashlib
import json
from pathlib import Path
from code.init import parse_input
from code.simulator import Simulator
from code.print_status import format_result, result_dict
from tests.reference import interpret


def main():
    root = Path(__file__).resolve().parent
    output = root / "results"
    output.mkdir(exist_ok=True)
    rows = []
    cases = [(p, "words") for p in sorted((root / "test_cases").glob("*.txt")) if p.name != "code_words.txt"]
    cases.append((root / "test_cases" / "legacy" / "test_case.txt", "bytes"))
    for path, mode in cases:
        reference = interpret(path, mode)
        label = "legacy_test_case" if mode == "bytes" else path.stem
        for width in range(1, 5):
            config, instructions, ints, floats, memory = parse_input(path)
            config.issue_width = width
            machine = Simulator(config, instructions, ints, floats, memory, mode)
            result = machine.run()
            committed = [e for e in result.history if e.commit is not None]
            correct = (result.reg_int == reference.reg_int and result.reg_fp == reference.reg_fp
                       and result.memory == reference.memory
                       and [e.pc * 4 for e in committed] == reference.committed_pcs)
            if not correct:
                raise AssertionError(f"Architectural mismatch: {label}, width={width}")
            basename = f"{label}_w{width}"
            (output / f"{basename}.txt").write_text(format_result(result))
            data = result_dict(result)
            data.update({"config": vars(config), "branch_offset_mode": mode,
                         "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "recovery_events": machine.events, "reference_match": True})
            (output / f"{basename}.json").write_text(json.dumps(data, indent=2) + "\n")
            rows.append({"test_case": label, "issue_width": width,
                         "cycles": result.cycles, **result.stats,
                         "reference_match": correct})
    with (output / "width_results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "width_results.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"Completed {len(rows)} width runs; all architectural states and committed paths match the independent interpreter.")


if __name__ == "__main__":
    main()
