"""Directed regressions for speculative state and provisional forwarding."""
from pathlib import Path
import tempfile
import unittest
from code.init import parse_input
from code.simulator import Simulator


class RecoveryEdgeTests(unittest.TestCase):
    def run_text(self, text, width=4):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "program.txt"
            path.write_text(text)
            config, instructions, integers, floats, memory = parse_input(path)
            config.issue_width = width
            return Simulator(config, instructions, integers, floats, memory).run(10000)

    def test_known_matching_store_survives_unknown_nonmatching_store(self):
        text = """Integer adder 4 8 1
FP adder 4 3 1
FP multiplier 4 20 1
Load/store unit 4 1 4 1
F1=9, F2=7
Mem[0]=1
Mult.d F31, F0, F0
Sd F1, 0(R0)
Addi R1, R0, 4
Sd F2, 0(R1)
Ld F3, 0(R0)
"""
        for width in range(1, 5):
            with self.subTest(width=width):
                result = self.run_text(text, width)
                self.assertEqual(result.reg_fp[3], 9)
                self.assertEqual(result.memory[4], 7)
                self.assertEqual(result.stats["replays"], 0)

    def test_faulting_wrong_path_load_does_not_supply_a_value(self):
        text = """Integer adder 4 6 1
FP adder 4 3 1
Load/store unit 4 1 4 1
Addi R1, R0, 1
Beq R1, R1, 2
Ld F2, -1(R0)
Add.d F3, F2, F2
Addi R2, R0, 7
"""
        result = self.run_text(text)
        self.assertEqual(result.reg_int[2], 7)
        self.assertEqual(result.reg_fp[3], 0)
        faulted = next(e for e in result.history if e.op == "ld")
        self.assertTrue(faulted.squashed)
        self.assertIsNone(faulted.wb)

    def test_younger_invalid_branch_target_waits_for_older_branch(self):
        text = """Integer adder 4 6 2
Addi R1, R0, 1
Beq R1, R1, 2
Beq R0, R0, 9999
Addi R2, R0, 99
Addi R2, R0, 7
"""
        result = self.run_text(text)
        self.assertEqual(result.reg_int[2], 7)
        younger = next(e for e in result.history if e.pc == 2)
        self.assertTrue(younger.squashed)
        self.assertIsNone(younger.commit)

    def test_invalid_correct_path_memory_address_is_reported(self):
        with self.assertRaisesRegex(ValueError, "Invalid memory byte address"):
            self.run_text("Ld F2, 256(R0)\n")


if __name__ == "__main__":
    unittest.main()
