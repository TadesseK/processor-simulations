"""Command-line entry point; no third-party packages are required."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from code.init import parse_input
from code.simulator import Simulator
from code.print_status import format_result, result_dict


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tomasulo simulation, issue width 1–4")
    parser.add_argument("input", nargs="?", default=str(Path(__file__).resolve().parents[1] / "test_cases" / "test_case_words.txt"))
    parser.add_argument("--issue-width", type=int, choices=range(1, 5))
    parser.add_argument("--branch-offset-mode", choices=("words", "bytes"), default="words",
                        help="Words follows the handout; bytes is explicit compatibility with starter -12")
    parser.add_argument("--max-cycles", type=int, default=100000)
    parser.add_argument("--output", type=Path, help="Write text status to this file")
    parser.add_argument("--json", type=Path, help="Write machine-readable status to this file")
    args = parser.parse_args(argv)
    try:
        config, instructions, reg_int, reg_fp, memory = parse_input(args.input)
        if args.issue_width is not None:
            config.issue_width = args.issue_width
        machine = Simulator(config, instructions, reg_int, reg_fp, memory, args.branch_offset_mode)
        result = machine.run(args.max_cycles)
        content = format_result(result)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content)
        else:
            print(content, end="")
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            data = result_dict(result)
            data.update({"config": vars(config), "branch_offset_mode": args.branch_offset_mode,
                         "recovery_events": machine.events})
            args.json.write_text(json.dumps(data, indent=2) + "\n")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
