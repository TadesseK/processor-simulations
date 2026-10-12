# Branch Predictor Implementation

This folder is the supplied `cbp2-infrastructure-v2` project renamed
`branch-prediction`. Its original relative layout is preserved: the required
implementation is `src/my_predictor.h`, and the 20 supplied traces are in
`traces/`.

The required predictor combines a 4,096-entry bimodal table and a two-way tagged
global table with 512 sets. A global hit overrides the bimodal prediction.
The predictor uses a 15-bit conditional global history register and a PC XOR
instead of the optional PIR and hash. The required assignment allows omission of
loop and target prediction; those components are not implemented.

## Build and run

Requirements: Linux or another Unix-like environment with C++17 `g++`, `make`,
Python 3, and `bzip2`. The reader also supports `gzip` and plain trace files.
No Python packages or downloaded libraries are needed.

From this folder:

```sh
make -C src
./src/predict traces/164.gzip/gzip.trace.bz2
./run traces
```

The direct simulator prints direction mispredictions per 1,000 instructions
(MPKI). `./run traces` evaluates all 20 complete traces and prints their average.
The portable Python `run` replaces the original C-shell runner.

To reproduce all results, including both comparison predictors and exact counts:

```sh
python3 evaluate.py --jobs 3
```

This builds `predict`, `predict_bimodal`, and `predict_gshare`, then executes all
60 complete-trace simulations. It creates `results/benchmark_results.csv`,
`exact_statistics.json`, `summary.json`, `run_manifest.json`, `build.log`, and
one command/output log per run in `results/raw_logs/`. Use `--jobs 1` to run
sequentially. Every benchmark has the supplied fixed denominator of 100 million
instructions. Each simulator process begins with a fresh predictor.

Exact statistics for one trace are also available directly:

```sh
./src/predict --json traces/164.gzip/gzip.trace.bz2
```

## Verify the predictor

```sh
make -C src test
g++ -std=c++17 -Wall -Wextra -Werror tests/appendix_trace.cc -o tests/appendix_trace
./tests/appendix_trace > tests/appendix_trace.csv
```

The unit tests cover saturation, fallback and override, valid bits and tags,
collisions, LRU, saved prediction-time indices, history masking, unconditional
branches, allocation policies, reset, and the handout's worked example. The
recorded run passed eight groups with 217 checks. All 22 published worked-example
rows matched; its input table also contains a 23rd event without a worked result.
See `tests/README.md` and `tests/test_results.txt` for details.

## Results and files

The hybrid averaged **7.2596035 MPKI**, compared with **10.2986085 MPKI** for the
bimodal component alone and **6.305859 MPKI** for the supplied 32,768-entry
gshare. The hybrid reduced bimodal misses by **29.5089%** and improved 19 of 20
benchmarks. The predictors use different table capacities. `report.md` explains the
implementation, code changes, worked examples, and measured results.

- `src/my_predictor.h`: implementation and baselines.
- `src/predict.cc`: supplied trace driver with optional exact JSON statistics.
- `tests/`: focused checks and reproducible appendix example.
- `results/`: exact counts, summary, hashes, build output, and run logs.
- `doc/index.html`: original infrastructure documentation, retained for reference.

The original compression utility in `src/compress/` is supplied background code;
it is not needed to build or execute this assignment. The optional
`predict_extra_credit.cc` driver and explicit predictor stub are retained, but
`run_extra` reports that the optional extension is not implemented. Normal
`make` builds only the completed required predictor.

## Changes to the supplied infrastructure

The predictor interface remains the supplied `predict`/`update` interface. The
target getter in `predictor.h` now returns `unsigned int` instead of `bool`,
matching its stored address type.
The trace reader now rejects missing/too-short files, quotes filenames before
opening the decompressor, checks the decompressor exit status, and uses `pclose`
for its pipe. Its decoding algorithm is unchanged. `evaluate.py` calls a new
optional `--json` driver format; the original one-line MPKI format still works.

The predictor, cache replacement logic, tests, and portable runner are written
for this submission. The trace reader, infrastructure interface, original
optional driver, and gshare algorithm derive from the supplied CBP2 project by
Daniel A. Jimenez. No third-party cache implementation was used.
