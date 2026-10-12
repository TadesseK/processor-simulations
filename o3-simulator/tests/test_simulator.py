"""Run with: python -m unittest discover -s tests -v"""

from collections import Counter
from dataclasses import replace
import hashlib
from pathlib import Path
import random
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code.init import parse_input
from code.simulator import Simulator
try:
    from tests.reference import interpret
except ImportError:
    from reference import interpret

CASES = ROOT / "test_cases"


class SimulatorTests(unittest.TestCase):
    def simulate(self, name, width=1, mode="words", **overrides):
        path = CASES / name
        config, program, integers, floats, memory = parse_input(path)
        config = replace(config, issue_width=width, **overrides)
        result = Simulator(config, program, integers, floats, memory,
                           branch_offset_mode=mode).run(max_cycles=10000)
        return config, result

    def assert_state(self, result, reference):
        self.assertEqual(result.reg_int, reference.reg_int)
        self.assertEqual(len(result.reg_fp), 32)
        self.assertEqual(len(result.memory), 256)
        for index, (actual, expected) in enumerate(zip(result.reg_fp, reference.reg_fp)):
            self.assertAlmostEqual(actual, expected, places=9, msg=f"F{index}")
        for address, (actual, expected) in enumerate(zip(result.memory, reference.memory)):
            self.assertAlmostEqual(actual, expected, places=9, msg=f"Mem[{address}]")
        committed = sorted((entry for entry in result.history if entry.commit is not None),
                           key=lambda entry: entry.commit)
        self.assertEqual([entry.pc * 4 for entry in committed], reference.committed_pcs)
        self.assertTrue(all(not entry.squashed for entry in committed))
        self.assertEqual(result.reg_int[0], 0)

    def assert_pipeline(self, config, result):
        issued = Counter(entry.issue for entry in result.history)
        self.assertTrue(all(amount <= config.issue_width for amount in issued.values()))
        writebacks = Counter(entry.wb for entry in result.history if entry.wb is not None)
        commits = Counter(entry.commit for entry in result.history if entry.commit is not None)
        self.assertTrue(all(amount <= 1 for amount in writebacks.values()), "single CDB")
        self.assertTrue(all(amount <= 1 for amount in commits.values()), "single commit")
        surviving = [entry for entry in result.history if entry.commit is not None]
        self.assertEqual([entry.seq for entry in sorted(surviving, key=lambda e: e.commit)],
                         sorted(entry.seq for entry in surviving), "ROB program order")
        for entry in surviving:
            self.assertEqual(len(entry.exe), 2)
            self.assertGreater(entry.exe[0], entry.issue)
            self.assertGreaterEqual(entry.exe[1], entry.exe[0])
            if entry.mem:
                self.assertEqual(len(entry.mem), 2)
                self.assertGreater(entry.mem[0], entry.exe[1])
            if entry.wb is not None:
                self.assertGreater(entry.wb, entry.mem[-1] if entry.mem else entry.exe[-1])
                self.assertGreater(entry.commit, entry.wb)
            elif entry.op == "sd":
                self.assertEqual(entry.commit, entry.mem[-1])
            else:
                self.assertIn(entry.op, {"beq", "bne"})
                self.assertGreater(entry.commit, entry.exe[-1])

    def test_architectural_state_and_timing_at_all_issue_widths(self):
        filenames = [path.name for path in CASES.glob("*.txt") if path.name != "code_words.txt"]
        for filename in sorted(filenames):
            reference = interpret(CASES / filename)
            for width in range(1, 5):
                with self.subTest(case=filename, width=width):
                    config, result = self.simulate(filename, width)
                    self.assert_state(result, reference)
                    self.assert_pipeline(config, result)

    def test_default_issue_width_and_case_insensitive_decoder(self):
        config, program, integers, floats, memory = parse_input(CASES / "sample_report_01.txt")
        self.assertEqual(config.issue_width, 1)
        config, program, integers, floats, memory = parse_input(CASES / "mixed_case.txt")
        self.assertEqual([entry.op for entry in program],
                         ["addi", "ld", "add.d", "sub.d", "mult.d", "sd", "bne", "add"])
        self.assertEqual(program[1].dest, "F10")

    def test_exact_legacy_fixtures_are_preserved(self):
        checksums = {
            "code.in": "f36b04294e8d9ddb6667e8d953370da6d3b1ad52056c8c657d52a078fd1daca9",
            "test_case.txt": "fcdcb1c5e7d335e716f54000bbdc6a90d18e8ec4a13e849ba800e4359cffe2f5",
        }
        for name, expected in checksums.items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((CASES / "legacy" / name).read_bytes()).hexdigest(), expected)

    def test_issue_width_must_be_between_one_and_four(self):
        contents = (CASES / "independent.txt").read_text()
        for width in (0, -1, 5):
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "bad_width.txt"
                path.write_text(contents.replace("Issue width = 1", f"Issue width = {width}"))
                with self.subTest(width=width), self.assertRaises(ValueError):
                    parse_input(path)

    def test_bundle_raw_dependencies(self):
        _, result = self.simulate("dependencies.txt", 4)
        first, second = result.history[:2]
        self.assertEqual(first.issue, second.issue)
        self.assertGreater(second.exe[0], first.wb)
        self.assertEqual(result.reg_int[4], 17)
        self.assertEqual(result.reg_fp[10], 9)

    def test_waw_and_war_capture_the_correct_versions(self):
        _, result = self.simulate("renaming.txt", 4)
        committed = [entry for entry in result.history if entry.commit is not None]
        self.assertGreater(committed[0].wb, committed[1].wb)
        self.assertEqual(result.reg_fp[2], 6)
        self.assertEqual(result.reg_fp[8], 9)
        self.assertEqual(result.reg_fp[12], 15)
        self.assertEqual(result.reg_fp[4], 8)
        self.assertEqual(result.reg_fp[14], 14)

    def test_r0_is_never_renamed_or_modified(self):
        for width in range(1, 5):
            with self.subTest(width=width):
                _, result = self.simulate("zero_register.txt", width)
                self.assertEqual(result.reg_int[:3], [0, 3, 3])
                self.assertEqual(result.memory[0], 7)
                self.assertEqual(result.reg_fp[4], 7)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nonzero_r0.txt"
            path.write_text("R0=23\nAddi R1, R0, 1\n")
            config, program, integers, floats, memory = parse_input(path)
            self.assertEqual(integers[0], 0)
            result = Simulator(config, program, integers, floats, memory).run(max_cycles=10000)
            self.assertEqual(result.reg_int[1], 1)

    def test_execution_is_out_of_order_and_commit_is_in_order(self):
        _, result = self.simulate("out_of_order.txt", 4)
        multiply, dependent, independent = result.history[:3]
        self.assertLess(independent.exe[0], dependent.exe[0])
        self.assertLess(independent.wb, multiply.wb)
        self.assertGreater(independent.commit, dependent.commit)

    def test_integer_unit_is_unpipelined(self):
        config, result = self.simulate("functional_units.txt", 4, int_fus=1)
        integers = [entry for entry in result.history if entry.op == "addi"]
        intervals = sorted(entry.exe for entry in integers)
        for start, end in intervals:
            self.assertEqual(end - start + 1, config.int_ex)
        for first, second in zip(intervals, intervals[1:]):
            self.assertGreater(second[0], first[1])

    def test_fp_units_are_pipelined(self):
        config, result = self.simulate("functional_units.txt", 4)
        additions = sorted((entry for entry in result.history if entry.op == "add.d"),
                           key=lambda entry: entry.exe[0])
        self.assertLess(additions[1].exe[0], additions[0].exe[1])
        self.assertEqual(additions[1].exe[0], additions[0].exe[0] + 1)
        multiplications = sorted((entry for entry in result.history if entry.op == "mult.d"),
                                key=lambda entry: entry.exe[0])
        self.assertLess(multiplications[1].exe[0], multiplications[0].exe[1])
        for entry in additions:
            self.assertEqual(entry.exe[1] - entry.exe[0] + 1, config.fp_add_ex)

    def test_functional_unit_counts_change_start_capacity(self):
        _, one = self.simulate("functional_units.txt", 4)
        config, two = self.simulate("functional_units.txt", 4,
                                    int_fus=2, fp_add_fus=2, fp_mul_fus=2, ls_fus=2)
        for op in ("addi", "add.d", "mult.d", "ld"):
            with self.subTest(op=op):
                one_starts = Counter(entry.exe[0] for entry in one.history if entry.op == op)
                two_starts = Counter(entry.exe[0] for entry in two.history if entry.op == op)
                self.assertEqual(max(one_starts.values()), 1)
                self.assertEqual(max(two_starts.values()), 2)
        self.assert_state(two, interpret(CASES / "functional_units.txt"))
        self.assert_pipeline(config, two)

    def test_memory_port_is_single_and_nonpipelined(self):
        config, result = self.simulate("memory_serial.txt", 4)
        intervals = sorted(entry.mem for entry in result.history if entry.mem)
        for start, end in intervals:
            self.assertEqual(end - start + 1, config.mem_cycles)
        for first, second in zip(intervals, intervals[1:]):
            self.assertGreater(second[0], first[1])

    def test_latest_matching_store_forwards_in_one_cycle(self):
        _, result = self.simulate("store_forwarding.txt", 4)
        stores = [entry for entry in result.history if entry.op == "sd"]
        loads = [entry for entry in result.history if entry.op == "ld"]
        self.assertEqual(loads[0].forwarded_from, stores[2].seq)
        self.assertEqual(loads[1].forwarded_from, stores[1].seq)
        for entry in loads:
            self.assertEqual(entry.mem[0], entry.mem[1])
        self.assertEqual(result.reg_fp[6], 9)
        self.assertEqual(result.reg_fp[10], 7)
        self.assertEqual(result.stats["forwarded_loads"], 2)

    def test_forwarding_search_skips_a_nonmatching_nearest_store(self):
        _, result = self.simulate("forward_past_nonmatching_store.txt", 4)
        store = next(entry for entry in result.history if entry.op == "sd")
        load = next(entry for entry in result.history if entry.op == "ld")
        self.assertEqual(load.forwarded_from, store.seq)
        self.assertEqual(result.reg_fp[6], 3)

    def test_load_waits_for_known_matching_store_data(self):
        _, result = self.simulate("memory_waiting_store_data.txt", 4)
        multiply = result.history[0]
        load = next(entry for entry in result.history if entry.op == "ld" and not entry.squashed)
        self.assertGreater(load.mem[0], multiply.wb)
        self.assertEqual(load.forwarded_from, result.history[1].seq)
        self.assertEqual(result.reg_fp[8], 12)

    def test_unresolved_older_store_alias_triggers_replay(self):
        _, result = self.simulate("memory_replay.txt", 4)
        store = next(entry for entry in result.history if entry.op == "sd")
        loads = [entry for entry in result.history if entry.op == "ld"]
        self.assertGreaterEqual(result.stats["replays"], 1)
        self.assertGreaterEqual(len(loads), 2)
        self.assertTrue(loads[0].squashed)
        self.assertIsNone(loads[0].commit)
        self.assertLess(loads[0].mem[0], store.exe[1])
        self.assertEqual(result.reg_fp[4], 9)
        self.assertEqual(result.reg_fp[6], 18)
        self.assert_state(result, interpret(CASES / "memory_replay.txt"))

    def test_unresolved_nonaliasing_store_does_not_replay(self):
        _, result = self.simulate("memory_nonalias.txt", 4)
        self.assertEqual(result.stats["replays"], 0)
        self.assertEqual(result.reg_fp[4], 1)
        self.assertEqual(result.reg_fp[6], 10)

    def test_branch_recovery_fetches_at_n_plus_two_and_squashes_store(self):
        _, result = self.simulate("branch_squash.txt", 4)
        branch = result.history[0]
        target = next(entry for entry in result.history if entry.pc == 3 and entry.commit is not None)
        self.assertEqual(target.issue, branch.exe[1] + 2)
        self.assertTrue(any(entry.squashed and entry.op == "sd" for entry in result.history))
        self.assertEqual(result.reg_int[2], 0)
        self.assertEqual(result.reg_int[3], 7)
        self.assertEqual(result.memory[16], 1)

    def test_rat_recovery_retains_older_pending_producer(self):
        _, result = self.simulate("branch_rat_recovery.txt", 4)
        target = next(entry for entry in result.history if entry.pc == 4 and entry.commit is not None)
        self.assertGreater(target.exe[0], result.history[0].wb)
        self.assertEqual(result.reg_fp[2], 12)
        self.assertEqual(result.reg_fp[8], 15)
        self.assertEqual(result.reg_fp[10], 0)

    def test_loop_predictor_learns_then_recovers_on_exit(self):
        _, result = self.simulate("branch_loop.txt", 4)
        self.assertEqual(result.stats["mispredictions"], 2)
        self.assertGreaterEqual(result.stats["btb_hits"], 1)
        self.assertEqual(result.reg_int[1:4], [0, 3, 13])

    def test_all_branch_conditions_and_program_end_target(self):
        for width in range(1, 5):
            for filename in ("branch_conditions.txt", "branch_skip_to_end.txt"):
                with self.subTest(width=width, case=filename):
                    _, result = self.simulate(filename, width)
                    self.assert_state(result, interpret(CASES / filename))

    def test_head_structural_hazard_blocks_younger_issue(self):
        _, result = self.simulate("head_of_line.txt", 4)
        multiply, blocked_multiply, integer = result.history
        self.assertGreater(blocked_multiply.issue, multiply.issue)
        self.assertGreaterEqual(integer.issue, blocked_multiply.issue)

    def test_tiny_rob_and_lsq_eventually_make_progress(self):
        for width in range(1, 5):
            with self.subTest(width=width):
                _, result = self.simulate("tiny_structures.txt", width)
                self.assert_state(result, interpret(CASES / "tiny_structures.txt"))
                self.assertLess(result.cycles, 10000)
                self.assertEqual(result.memory[12], 4)

    def test_legacy_byte_offsets_match_translated_word_offsets(self):
        reference = interpret(CASES / "legacy" / "test_case.txt", "bytes")
        for width in range(1, 5):
            with self.subTest(width=width):
                _, legacy = self.simulate("legacy/test_case.txt", width, "bytes")
                _, normalized = self.simulate("test_case_words.txt", width)
                self.assert_state(legacy, reference)
                self.assert_state(normalized, reference)
                self.assertEqual(legacy.cycles, normalized.cycles)

    def test_intended_full_loop_has_hand_calculated_results(self):
        _, result = self.simulate("full_loop.txt", 4)
        self.assertEqual(result.reg_int[1], 0)
        self.assertEqual(result.reg_int[2], 20)
        self.assertEqual([result.memory[address] for address in (24, 28, 32)], [15, 11, 7])
        self.assertEqual(result.reg_fp[20], 6)

    def test_seeded_programs_match_independent_interpreter(self):
        for seed in range(6):
            rng = random.Random(seed)
            lines = ["R1=4, R2=8, R3=12, F1=1.5, F2=2.0, F3=-0.5",
                     "Mem[4]=2, Mem[8]=-1, Mem[12]=3"]
            for _ in range(36):
                op = rng.choice(("add", "sub", "addi", "add.d", "sub.d", "mult.d", "ld", "sd"))
                a, b, c = [rng.randint(1, 10) for _ in range(3)]
                if op in ("add", "sub"):
                    lines.append(f"{op} R{a}, R{b}, R{c}")
                elif op == "addi":
                    lines.append(f"Addi R{a}, R{b}, {rng.randint(-5, 5)}")
                elif op in ("add.d", "sub.d", "mult.d"):
                    lines.append(f"{op} F{a}, F{b}, F{c}")
                else:
                    lines.append(f"{op} F{a}, {rng.choice((4, 8, 12, 16, 20))}(R0)")
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "random.txt"
                path.write_text("\n".join(lines) + "\n")
                reference = interpret(path)
                for width in range(1, 5):
                    with self.subTest(seed=seed, width=width):
                        config, program, integers, floats, memory = parse_input(path)
                        config = replace(config, issue_width=width)
                        result = Simulator(config, program, integers, floats, memory).run(max_cycles=10000)
                        self.assert_state(result, reference)
                        self.assert_pipeline(config, result)


if __name__ == "__main__":
    unittest.main()
