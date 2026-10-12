# October homework requirements checklist

The checklist follows the requirements in the two assignment handouts.

## Branch predictor

- [x] Implement the constructor, `predict`, and `update` of the supplied `pm_predictor` in `branch-prediction/src/my_predictor.h`. The original infrastructure's internal folder structure is preserved beneath the renamed `branch-prediction` root.
- [x] Combine an address-indexed bimodal table and a tagged global outcome predictor. A global hit supplies the final direction; a miss uses bimodal prediction.
- [x] Follow the diagram: 4,096 bimodal two-bit counters, 512 global sets with six-bit tags. Use the expressly permitted two-way global organization.
- [x] Document the allowed simplified history/XOR indexing and all initialization, allocation, update, and replacement choices.
- [x] Build the supplied C++ infrastructure with `make`; evaluate complete supplied traces and report measured direction MPKI.
- [x] Include source code, a results report, README and reproducible commands. Cite any reused external cache code; no external cache code is needed here.
- [x] Clearly identify the permitted exclusions: loop predictor, branch targets, PIR and the exact hardware hash. Extra-credit stubs are not required work.
- [ ] Submit the required code, report, and README to GitHub.

## Tomasulo simulator

- [x] Start from the supplied Python simulator and explain additions and repairs in the report.
- [x] Parse issue width 1-4 from input, default to 1, and issue in program order without skipping an instruction stalled by a full ROB, RS or LSQ.
- [x] Preserve five stages (ISSUE, EX, MEM, WB, COMMIT), register renaming, ROB, speculation and memory disambiguation.
- [x] Support every stated instruction: `Ld`, `Sd`, `Beq`, `Bne`, `Add`, `Addi`, `Sub`, `Add.d`, `Sub.d`, `Mult.d`; accept case-insensitive assembly and the provided input syntax.
- [x] Read RS counts, FU counts, EX latencies, memory latency, ROB size, register initialization and memory initialization from input.
- [x] Model 32 integer and 32 FP registers, zero defaults, hardwired R0, and 256-byte/64-word memory with byte addresses.
- [x] Keep the integer ALU unpipelined, FP units pipelined, memory single-ported and nonpipelined, and WB limited by one CDB.
- [x] Calculate load/store addresses with a dedicated adder; enqueue LSQ entries in order; forward from the newest matching older store in one cycle; clear completed load entries.
- [x] Write stores only at in-order commit and retain their LSQ entries until then; preserve correctness for loads that pass unresolved older stores.
- [x] Implement one-bit branch prediction per static branch, an eight-entry BTB indexed by the low three bits of the word PC, and resolution at the end of EX.
- [x] On misprediction restore the RAT, remove younger work from RS/ROB and other pending structures, spend one recovery cycle, then resume correct issue in cycle n+2.
- [x] Print the final dynamic instruction status with ISSUE/EX/MEM/WB/COMMIT cycles, final registers and nonzero memory values.
- [x] Include provided tests and original tests that verify widths 1, 2, 3 and 4; run them and include real results under different widths in the report.
- [x] Include runnable code, all test inputs, a simple README and report; disclose any remaining bugs or verification limits.
- [ ] Submit code, test cases, report, and README to GitHub.

## Conflicts resolved

1. The branch handout misspells `pm_predictor`; the starter's actual class name and driver are used.
2. The uploaded 2002 paper concerns P6/NetBurst, whereas the handout's Pentium M diagram cites a 2009 paper. The supplied diagram was used for the implementation.
3. The sample Tomasulo report widens WB/commit and omits branch support. It is an example report, not a replacement for the assignment hardware specification. The implementation preserves a single CDB and in-order single commit and supports branches.
4. The supplied Tomasulo `Bne ... -12` uses the old starter's byte displacement. The specified ISA uses a word displacement. Preserve the original fixture in explicit byte-offset mode and also provide a normalized word-offset fixture; never change interpretation silently.
5. The illustrative Tomasulo input has a loop without a terminating update. Treat it as a syntax example rather than a finite correctness benchmark; use terminating test programs for measured results. Byte addresses are accepted without an extra alignment restriction, consistent with the example.

## Verification results

| Verification | Actual result | Evidence |
|---|---|---|
| Uploaded archive integrity | Passed | Archive entries extract without CRC errors |
| Branch trace preservation | All 20 supplied traces identical byte for byte | Trace hashes in `branch-prediction/results/run_manifest.json` |
| Branch focused checks | 8 groups, 217 checks passed | `branch-prediction/tests/test_results.txt` |
| Branch handout example | All 22 published prediction rows matched | `branch-prediction/tests/appendix_trace.csv` |
| Branch benchmark evaluation | 60 complete runs: 20 traces for each of 3 predictors | `branch-prediction/results/benchmark_results.csv` and raw logs |
| Tomasulo regression suite | 30 test methods passed | `o3-simulator/results/verification.log` |
| Tomasulo issue-width experiments | All 104 runs matched final state and committed path | `o3-simulator/results/width_results.csv` and complete traces |
| Additional independent verifier | 1,000 seeded runs plus 4 directed cases passed | `o3-simulator/review/independent_verifier.py` and `verification.txt` |
