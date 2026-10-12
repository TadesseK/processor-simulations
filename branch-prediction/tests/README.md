# Predictor verification

Run from `branch-prediction/`:

```sh
g++ -std=c++17 -Wall -Wextra -Werror tests/test_predictor.cc -o tests/test_predictor
./tests/test_predictor
g++ -std=c++17 -Wall -Wextra -Werror tests/appendix_trace.cc -o tests/appendix_trace
./tests/appendix_trace > tests/appendix_trace.csv
```

The tests check two-bit counter saturation, the bimodal fallback and global
override, valid bits and tag collisions, invalid-first allocation and two-way
LRU replacement, prediction-time indices, the history mask, unconditional
branches, both allocation policies, and deterministic reset.

The appendix check runs the actual predictor template with the handout's small
configuration: 16 bimodal counters, four global sets, two ways, two-bit tags,
four-bit history, and a two-bit address shift. It seeds the counters exactly as
shown in the example and preserves each victim's counter before training it.
The main predictor instead initializes a new global entry weakly toward the
observed direction, as described in the report.

All 22 rows match the handout's main prediction-results table. There are nine
wrong and 13 correct direction predictions. The separate global-state table
prints a different direction on three global misses: rows 5 and 19 print T
although the bimodal fallback is NT, and row 22 prints NT although the fallback
is T. A direction printed for a missed global entry is not selected; the check
follows the main hybrid-results table and its stated bimodal fallback rule.
The 23rd event appears only in the input history; the worked results end at
event 22, so this check covers the 22 supplied result rows.

`test_results.txt` and `appendix_trace.csv` record the executed checks. The unit
tests also passed when compiled with address and undefined-behavior sanitizers.
Leak detection was disabled for that run because LeakSanitizer could not inspect
the process in this execution environment; the original diagnostic is retained
in the test log.

## Production walkthrough in the report

`production_walkthrough.cc` executes the eight artificial conditional branches
in the report using the actual cold `pm_predictor`. It prints the saved lookup
indices, chosen prediction, counter states, replacement victim, and history.
The recorded CSV is in `results/production_walkthrough.csv`.

From `branch-prediction/`, reproduce it with:

```sh
g++ -std=c++17 -Wall -Wextra -Werror tests/production_walkthrough.cc -o /tmp/production_walkthrough
/tmp/production_walkthrough > results/production_walkthrough.csv
```

This illustrates production transitions; it is separate from the 20 benchmark
traces and the appendix's smaller configuration.
