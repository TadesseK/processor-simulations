# Processor Simulations

This repository contains two computer architecture projects: a **hybrid branch predictor in C++** and a **multi-issue Tomasulo simulator in Python**. Each includes source code, a detailed report, test inputs, automated checks, and measured results.

The branch predictor studies how recent branch outcomes help predict the direction of a conditional branch. The Tomasulo simulator studies how instructions are scheduled, how dependencies are tracked, and how increasing issue width affects execution time.

## Contents

- [Project overview](#project-overview)
- [Repository organization](#repository-organization)
- [Requirements and quick start](#requirements-and-quick-start)
- [Hybrid branch predictor](#hybrid-branch-predictor)
- [Multi-issue Tomasulo simulator](#multi-issue-tomasulo-simulator)
- [Verification](#verification)
- [Reports and saved results](#reports-and-saved-results)

## Project overview

| Project | Main question | Implementation | Measurements |
| --- | --- | --- | --- |
| Hybrid branch predictor | Can branch history improve prediction compared with bimodal prediction alone? | C++17, trace-driven prediction and training | Direction mispredictions, MPKI, conditional miss rate |
| Multi-issue Tomasulo simulator | How does wider issue affect execution time under dependencies and resource limits? | Python, cycle-by-cycle instruction scheduling | Total cycles, stage timings, stalls, branch recovery, memory replay |

These are separate programs. The predictor processes recorded branch traces; the Tomasulo simulator executes assembly programs. They do not share a pipeline or combine their measurements into one processor model.

## Repository organization

| Path | Contents |
| --- | --- |
| [`branch-prediction/`](branch-prediction/) | Branch project, README, PDF report, and editable report source |
| [`branch-prediction/src/`](branch-prediction/src/) | Predictor, baselines, trace driver, trace reader, and Makefile |
| [`branch-prediction/traces/`](branch-prediction/traces/) | All 20 supplied compressed traces |
| [`branch-prediction/tests/`](branch-prediction/tests/) | Predictor checks and worked trace example |
| [`branch-prediction/results/`](branch-prediction/results/) | Exact counts, benchmark summaries, plot, and execution logs |
| [`o3-simulator/`](o3-simulator/) | Tomasulo project, README, PDF report, and editable report source |
| [`o3-simulator/code/`](o3-simulator/code/) | Input parser, controller, instruction stages, and output formatting |
| [`o3-simulator/test_cases/`](o3-simulator/test_cases/) | Programs covering dependencies, branches, memory, and resource limits |
| [`o3-simulator/tests/`](o3-simulator/tests/) | Automated checks and independent sequential interpreter |
| [`o3-simulator/results/`](o3-simulator/results/) | Timing tables, final states, JSON traces, plot, and width comparisons |
| [`REQUIREMENTS_CHECKLIST.md`](REQUIREMENTS_CHECKLIST.md) | Assignment requirements and completion checklist |
| [`verify_all.sh`](verify_all.sh) | Builds the predictor and runs both correctness suites |
| [`MANIFEST.sha256`](MANIFEST.sha256) | Checksums for the included submission files |

## Requirements and quick start

Use Linux, WSL, or another Unix-like environment with:

| Tool | Purpose |
| --- | --- |
| Python 3.10 or newer | Simulator, experiment scripts, and branch runner |
| C++17 compiler, such as `g++` | Predictor compilation |
| GNU Make | Build targets and predictor checks |
| `bzip2` and `gzip` | Compressed trace reading |

The simulator and experiment scripts use the Python standard library. No GPU, external API, or third-party Python package is needed to execute the programs and checks.

```bash
git clone https://github.com/TadesseK/processor-simulations.git
cd processor-simulations
bash verify_all.sh
```

Commands below start from the repository root unless another working directory is shown.

## Hybrid branch predictor

### Purpose

A conditional branch either jumps to its target (**taken**) or continues to the next instruction (**not taken**). The predictor estimates that direction before the outcome is known, then learns from the resolved outcome.

A bimodal predictor uses a branch's address to learn its usual direction. Global history adds the outcomes of recent branches, allowing prediction to reflect earlier control-flow decisions. The implemented `pm_predictor` combines both approaches in [`src/my_predictor.h`](branch-prediction/src/my_predictor.h).

### Components

| Component | Configuration | Role |
| --- | --- | --- |
| Bimodal table | 4,096 two-bit counters | Learns direction using the branch address |
| Global history register | 15 bits | Records recent conditional outcomes |
| Tagged global table | 512 sets, two ways per set | Stores predictions associated with the address-history hash |
| Global tag | Six bits per entry | Checks the selected entry against the current hash tag |
| Valid bit | One per global entry | Prevents unused entries from producing a hit |
| Replacement state | Two-way least recently used policy | Selects a victim when both ways are occupied |

Counters range from 0 to 3. Values 0 and 1 predict not taken; values 2 and 3 predict taken. Training moves a counter toward the observed outcome without exceeding either endpoint.

### Prediction and update sequence

1. The branch address selects a bimodal counter.
2. The address is XORed with the current global history. The 15-bit result supplies a nine-bit set index and a six-bit tag.
3. Both ways of the global set are checked for a valid matching tag.
4. A global hit supplies the final direction, overriding the bimodal prediction. A miss uses the bimodal direction.
5. After resolution, the bimodal counter and matching global counter are trained. A global miss allocates an entry, using an invalid way before replacing the least recently used way.
6. The resolved outcome enters the history register, which is masked to 15 bits.

Prediction-time indices are saved before history changes, so the update trains the entries used for that prediction. Unconditional branches return taken and do not train the conditional predictor state.

### Implementation changes

The starter's constant taken prediction was replaced with table lookup, tag matching, counter training, allocation, replacement, and history updates. Bimodal and gshare predictors are included for comparison.

The driver keeps its normal MPKI output and adds optional JSON statistics. A Python runner evaluates all supplied traces. The trace reader checks missing or incomplete files and decompressor failures. The target getter now returns the unsigned integer address type used by the interface.

The measured task is branch **direction** prediction. Loop prediction and target prediction are outside the implemented assignment components.

### Build and run

Build and run one trace:

```bash
make -C branch-prediction/src
./branch-prediction/src/predict branch-prediction/traces/164.gzip/gzip.trace.bz2
```

Request exact statistics:

```bash
./branch-prediction/src/predict --json branch-prediction/traces/164.gzip/gzip.trace.bz2
```

Evaluate the hybrid on all 20 traces:

```bash
python3 branch-prediction/run branch-prediction/traces
```

Reproduce the full three-predictor comparison:

```bash
python3 branch-prediction/evaluate.py --jobs 3
```

This performs 60 complete-trace runs: 20 traces for each predictor. Use `--jobs 1` for sequential execution. Each run starts with fresh predictor state.

### Measured results

MPKI means **mispredictions per 1,000 instructions**:

```text
MPKI = 1,000 × direction mispredictions / instruction count
```

The supplied convention uses 100 million instructions per trace. Lower MPKI indicates fewer direction errors.

| Predictor | Average MPKI across 20 traces | Total direction mispredictions |
| --- | ---: | ---: |
| Bimodal | 10.2986085 | 20,597,217 |
| Hybrid | 7.2596035 | 14,519,207 |
| Supplied gshare | 6.3058590 | 12,611,718 |

The hybrid reduced average MPKI by **29.5089%** compared with bimodal and improved **19 of 20** benchmarks. Gshare had lower MPKI than the hybrid on 19 benchmarks. Its 32,768-entry table differs in capacity from the hybrid configuration, so these results compare the supplied configurations rather than equal-storage designs.

Per-trace results are in [`benchmark_results.csv`](branch-prediction/results/benchmark_results.csv), with aggregates in [`summary.json`](branch-prediction/results/summary.json). The report includes source excerpts, a worked prediction sequence, and interpretation of the measurements.

## Multi-issue Tomasulo simulator

### Purpose

Tomasulo scheduling lets an instruction execute when its operands and functional unit are ready, even when an older instruction is waiting. Register renaming identifies the producer of each pending value. A reorder buffer preserves program order when results become visible in architectural registers and memory.

This project extends the supplied simulator to issue **one, two, three, or four instructions per cycle**. Wider issue allows more instructions to enter the scheduling structures; dependencies and hardware limits still determine when they execute and retire.

### Supported instructions and configuration

| Category | Instructions |
| --- | --- |
| Integer arithmetic | `ADD`, `SUB`, `ADDI` |
| Floating-point arithmetic | `ADD.D`, `SUB.D`, `MULT.D` |
| Memory | `LD`, `SD` |
| Conditional branches | `BEQ`, `BNE` |

The input specifies reservation station counts, functional unit counts, execution latencies, memory latency, reorder buffer capacity, issue width, initial registers, and initial memory. There are 32 integer and 32 floating-point registers. `R0` remains zero.

### Instruction stages

| Stage | Operation |
| --- | --- |
| ISSUE | Enters instructions in program order, captures values or producer tags, allocates resources, and renames destinations |
| EX | Executes ready instructions on available units; computes load and store addresses |
| MEM | Obtains load values from memory or an older matching store |
| WB | Broadcasts at most one result per cycle on the common data bus |
| COMMIT | Retires at most one instruction per cycle in program order and updates architectural state |

A structural hazard ends the current issue bundle. Younger instructions cannot bypass the blocked instruction during issue. Once issued, ready instructions can execute out of order.

### Dependencies and recovery

- **Operand tracking:** Waiting instructions retain producer tags and receive values when those producers broadcast. A consumer executes after its producer's write-back cycle.
- **Register renaming:** Sources are captured before the destination is renamed. Later instructions in the same issue bundle see earlier producers correctly. An older instruction's commit does not erase a newer mapping for the same register.
- **In-order retirement:** Completed instructions wait for older instructions to retire. Speculative results do not immediately modify architectural state.
- **Branch recovery:** A one-bit direction predictor and a tagged eight-entry branch target buffer guide fetching. A misprediction removes younger work and restores register mappings. Fetching resumes two cycles after resolution.
- **Store forwarding:** A load uses the newest known older matching store. If the store's data is unavailable, the load waits.
- **Memory replay:** A load can proceed while an older store address is unknown. A later-resolved superseding alias causes the affected load and younger instructions to replay.

Increasing issue width preserves one common data bus, one commit per cycle, and one nonpipelined physical memory port. Integer and address-calculation units are unpipelined; floating-point adders and multipliers are pipelined. These constraints explain why wider issue does not always reduce cycle counts.

### Implementation changes

The implementation adds configurable multi-issue scheduling and a controller while retaining the ISSUE, EX, MEM, WB, and COMMIT modules. The state representation tracks dynamic instructions, dependencies, stage cycles, and recovery.

The changes also repair register mapping updates, store retirement, forwarding selection, and memory ordering. Added programs exercise same-cycle issue dependencies, renaming, branch recovery, forwarding, replay, and limited resources. An independent sequential interpreter checks final registers, memory, and the committed instruction path.

### Run a program

From the repository root:

```bash
cd o3-simulator
python3 code/main.py test_cases/test_case_words.txt --issue-width 4
```

Run the full loop and save its output:

```bash
python3 code/main.py test_cases/full_loop.txt --issue-width 3 --output result.txt --json result.json
```

Text output includes stage timings, total cycles, final registers, and memory state. JSON also records configuration, statistics, and recovery events.

The default branch offset is a signed displacement in words, following `PC + 4 + (offset << 2)`. Run the preserved original input using its explicit byte-offset convention:

```bash
python3 code/main.py test_cases/legacy/test_case.txt --branch-offset-mode bytes --issue-width 2
```

Without an input argument, the default is `test_cases/test_case_words.txt`. The command-line issue width overrides the input setting; the default is one when omitted. `--max-cycles` sets the execution limit.

### Reproduce the issue-width experiment

From `o3-simulator/`:

```bash
python3 run_experiments.py
```

The script evaluates 26 program configurations at widths 1, 2, 3, and 4, producing **104 runs**. Each run checks final registers, memory, and the committed instruction path against the independent interpreter. Timing tables and JSON traces are saved alongside combined CSV and JSON summaries.

### Measured results

| Program | Width 1: cycles | Width 2: cycles | Width 3: cycles | Width 4: cycles |
| --- | ---: | ---: | ---: | ---: |
| Independent instructions | 18 | 16 | 15 | 15 |
| Dependency program | 25 | 22 | 21 | 21 |
| Full load and store loop | 66 | 65 | 65 | 65 |
| Supplied normalized program | 45 | 45 | 45 | 45 |
| Memory replay program | 24 | 24 | 24 | 24 |

Independent instructions benefit when wider issue makes ready work available earlier. Dependency chains, long execution latencies, memory access, and single-result write-back or commit limit further improvement. Several programs therefore have unchanged cycle counts.

All **104 configurations** matched the independent interpreter. Full measurements are in [`width_results.csv`](o3-simulator/results/width_results.csv) and [`width_results.json`](o3-simulator/results/width_results.json).

## Verification

Run both correctness suites from the repository root:

```bash
bash verify_all.sh
```

Run the branch checks separately:

```bash
make -C branch-prediction/src test
```

Run the simulator checks separately:

```bash
cd o3-simulator
python3 -m unittest discover -s tests -v
```

| Check | Recorded result | Coverage |
| --- | --- | --- |
| Branch suite | Eight groups, 217 checks passed | Counters, tags, fallback, override, replacement, history, allocation, reset, and worked example |
| Tomasulo suite | 30 tests passed | Dependencies, timing, resources, renaming, forwarding, replay, and branch recovery |
| Experiment comparison | 104 runs matched | Final architectural states and committed instruction paths at all four issue widths |

Saved logs accompany the results. `verify_all.sh` runs the correctness suites; the experiment scripts separately reproduce full benchmark measurements.

## Reports and saved results

- [Branch Prediction Report](branch-prediction/report.pdf): implementation changes, source excerpts, worked examples, and trace results.
- [Tomasulo Report](o3-simulator/report.pdf): code changes, test programs, issue-width results, and instruction timing tables.
- [Branch project README](branch-prediction/README.md): additional build, evaluation, and file details.
- [Tomasulo project README](o3-simulator/README.md): input format, command options, and timing conventions.
- [Tomasulo starter changes](o3-simulator/STARTER_CHANGES.md): detailed changes to the supplied simulator.

The supplied branch trace reader and infrastructure, including the gshare comparison algorithm, originate from Daniel A. Jimenez's CBP2 project. The hybrid implementation and project tests extend that infrastructure. The Tomasulo implementation extends the supplied stage-based Python starter.
