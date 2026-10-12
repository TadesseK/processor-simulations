# Test cases

Run all checks from the project directory with:

```sh
python -m unittest discover -s tests -v
```

The suite runs every complete fixture at issue widths 1, 2, 3, and 4. It compares
all 32 integer registers, all 32 floating-point registers, all 256 byte-addressed
memory locations, and the committed dynamic instruction sequence with the
independent sequential interpreter in `tests/reference.py`. Timing checks cover
issue capacity, one CDB, one commit, pipeline stage separation, and ROB order.

| Fixture | Main check |
| --- | --- |
| `independent.txt` | Independent instruction issue and execution |
| `dependencies.txt` | RAW dependencies, including instructions in one issue bundle |
| `renaming.txt` | WAW, WAR, and selection of the latest register version |
| `zero_register.txt` | R0 initialization and writes remain zero |
| `out_of_order.txt` | Younger independent work executes before blocked older work |
| `functional_units.txt` | Integer serialization, FP pipelining, and configurable FU counts |
| `memory_serial.txt` | Single-port, nonpipelined memory access |
| `store_forwarding.txt` | Forwarding from the youngest matching older store |
| `forward_past_nonmatching_store.txt` | Search beyond a nonmatching nearest store |
| `memory_waiting_store_data.txt` | Wait for the data of a known matching store |
| `memory_replay.txt` | Speculative load replay when an unresolved older store aliases |
| `memory_nonalias.txt` | No replay when the unresolved store resolves to another address |
| `branch_squash.txt` | Correct fetch at resolution cycle + 2; wrong-path store has no effect |
| `branch_rat_recovery.txt` | Restore an older pending producer after branch recovery |
| `branch_loop.txt` | One-bit prediction learns a loop and recovers on exit |
| `branch_btb_alias.txt` | Branches at PC 0 and PC 32 share an eight-entry BTB index |
| `branch_conditions.txt` | Taken and untaken BEQ and BNE |
| `branch_skip_to_end.txt` | Recovery with a target immediately after the final instruction |
| `head_of_line.txt` | A structural hazard blocks younger instruction issue |
| `tiny_structures.txt` | Progress with a two-entry ROB and one-entry LSQ |
| `mixed_case.txt` | Case-insensitive text, two-digit registers, commas, and byte addresses |
| `sample_report_01.txt`, `sample_report_02.txt` | The two supplied report configurations and instruction lists |
| `full_loop.txt` | Three load/multiply/add/store iterations with a word offset of -8 |

`legacy/code.in` and `legacy/test_case.txt` are byte-for-byte copies of the
provided files. The original branch uses `-12` as a byte displacement.
`code_words.txt` and `test_case_words.txt` change only that displacement to `-3`
for the assignment's word-offset ISA. Both interpretations branch from PC 28 to
PC 20 and therefore repeat the pointer updates, rather than the entire
load/store body. The separate `full_loop.txt` uses `-8` to return to PC 0.

`legacy/code.in` and `code_words.txt` contain instructions only; use the register,
memory, and hardware initialization in the complete `test_case.txt` variants to
run the provided example. Running the instruction-only fragment with all-zero
registers would not terminate.

The sample report changes writeback and commit width and allows overlapping
memory accesses. Those example timing tables are not used as expected answers
because the assignment specifies one CDB and single-port nonpipelined memory.
The sample programs' final architectural results are checked independently.

The suite also checks invalid issue widths, the legacy file checksums, and six
seeded 36-instruction mixed programs at all four widths. Random seeds are fixed
so these checks can be reproduced.
