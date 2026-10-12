# Tomasulo multiple-issue simulator

This submission extends the supplied stage-based Python simulator to issue 1–4 instructions in program order. It supports all instructions in the assignment, register renaming, out-of-order execution, one CDB, an in-order ROB, branch prediction and recovery, and load/store disambiguation.

Python 3.10 or newer is required. There are no third-party dependencies.

## Run

From this directory:

```sh
python code/main.py
python code/main.py test_cases/test_case_words.txt --issue-width 4
python code/main.py test_cases/legacy/test_case.txt --branch-offset-mode bytes --issue-width 2
python code/main.py test_cases/full_loop.txt --issue-width 3 --output result.txt --json result.json
```

The default input is `test_cases/test_case_words.txt`. Issue width defaults to 1 when the input omits it. `--issue-width` overrides the input setting. The default branch offset is a signed word displacement, as specified by `PC + 4 + (offset << 2)`. The explicit `bytes` mode handles the original starter's `-12` displacement without changing the original file.

Run the checks and reproduce the results:

```sh
python -m unittest discover -s tests -v
python run_experiments.py
```

`results/tests.log` records the submitted test run. `results/width_results.csv` and `results/width_results.json` summarize all 104 benchmark runs. Every run also has a text status table and JSON trace containing the complete register state, nonzero memory, stage cycles, recovery events, input hash, and configuration.

## Input

The parser accepts the assignment's hardware table, initialization lines, and case-insensitive assembly. Commas between operands are optional. `#`, `//`, and `;` start comments.

```text
               # of RS   Cycles in EX   Cycles in MEM   # of FUs
Integer adder   4         1                             1
FP adder        3         3                             1
FP multiplier   2         20                            1
Load/store unit 4         1              4              1

ROB entries = 128
Issue width = 2
R1=12, R2=32, F20=3.0
Mem[12]=1.0, Mem[32]=4.0

Ld F2, 0(R1)
Mult.d F4, F2, F20
Addi R1, R1, -4
```

All resource counts and latencies must be positive integers. Issue width must be 1–4. If an entire configuration setting is omitted, the handout's default example is used: RS counts 2/3/2/3; EX cycles 1/3/20/1; memory cycles 4; one unit of each kind; 128 ROB entries. Integer and FP register indices are 0–31. Nonzero R0 initialization is rejected, and instruction writes to R0 are discarded.

Memory is the starter's abstract, byte-addressed array of numeric values at addresses 0–255. It does not pack floating-point values into physical bytes. Unaligned addresses are accepted because the handout's syntax example accesses address 18 and states no alignment restriction. Load/store values and FP arithmetic use Python floating-point numbers, without IEEE instruction-level rounding or overflow modeling.

## Timing and hardware choices

- ISSUE is in order. A structural hazard ends the current issue bundle; later instructions cannot bypass it. Earlier instructions in a bundle update the RAT before later instructions capture their operands.
- Integer and effective-address units are unpipelined. FP adders and multipliers are pipelined and can accept one operation per configured FU each cycle. Reservation stations are released when an operation dispatches into its FU, following the starter's convention.
- The CDB broadcasts at most one result per cycle, and the ROB commits at most one instruction per cycle. Increasing issue width leaves these two limits unchanged.
- Memory has one nonpipelined physical access port, regardless of the number of address-calculation FUs. Forwarding takes one MEM cycle and uses the forwarding path rather than the memory port; at most one load starts MEM per cycle.
- A consumer cannot execute in its producer's WB cycle. Normal arithmetic/load commit follows WB in a later cycle. Branches resolve at EX and do not use the CDB. Stores use memory during commit and retire when that access finishes; their WB field is blank.
- The branch predictor uses one direction bit per static branch and a tagged eight-entry direct-mapped BTB indexed by the low three bits of the word PC. A misprediction at cycle n squashes younger work and restores the RAT; fetch resumes at n+2.
- A load can pass older stores with unknown addresses. It forwards the newest known matching store provisionally, or reads memory if no known match exists. A later-resolved superseding alias replays the oldest affected load and its younger instructions. A known matching store with unavailable data blocks that load until the data is ready.
- Status rows describe dynamic instructions. Squashed rows are retained and marked; an interrupted EX/MEM interval ends at its squash cycle. Only committed instructions change architectural registers or memory.

A correct-path invalid memory address or branch target is reported as an error at retirement. Speculative invalid operations can be squashed by an older branch. `--max-cycles` bounds accidental infinite loops; the default is 100,000 cycles.

## Files

| Path | Contents |
| --- | --- |
| `code/` | Parser/state types, controller, and the original ISSUE/EX/MEM/WB/COMMIT module organization |
| `test_cases/` | Original fixtures, normalized branch variants, both sample-report programs, and directed tests |
| `tests/` | Independent sequential ISA interpreter and automated architectural/timing checks |
| `run_experiments.py` | Reproducible runs at widths 1, 2, 3, and 4 |
| `results/` | Actual status tables, JSON traces, CSV summary, and final verification logs |
| `STARTER_CHANGES.md` | Changes and necessary repairs to the supplied code |
| `report.md` | Assignment report and measured different-width results |

The original instruction-only `code.in` lacks the starter's hardcoded initialization. With zero-initialized registers it does not terminate. Use its complete `test_case.txt` counterpart for the supplied benchmark. The original branch goes back to the pointer updates only; `full_loop.txt` separately tests the full load/store loop using a word offset of -8.
