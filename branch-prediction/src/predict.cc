// Driver from the supplied CBP2 infrastructure. The normal output format is
// unchanged; --json adds exact counts for reproducible results and aggregation.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "branch.h"
#include "trace.h"
#include "predictor.h"
#include "my_predictor.h"

#ifndef PREDICTOR_TYPE
#define PREDICTOR_TYPE pm_predictor
#endif
#ifndef PREDICTOR_NAME
#define PREDICTOR_NAME "hybrid"
#endif

int main(int argc, char *argv[]) {
    bool json = argc == 3 && strcmp(argv[1], "--json") == 0;
    if ((!json && argc != 2) || (argc == 3 && !json)) {
        fprintf(stderr, "Usage: %s [--json] <trace-file>\n", argv[0]);
        return 1;
    }
    char *filename = argv[json ? 2 : 1];
    init_trace(filename);
    branch_predictor *predictor = new PREDICTOR_TYPE();
    unsigned long long branches = 0, conditional = 0, misses = 0;
    for (;;) {
        trace *record = read_trace();
        if (!record) break;
        ++branches;
        branch_update *prediction = predictor->predict(record->bi);
        if (record->bi.br_flags & BR_CONDITIONAL) {
            ++conditional;
            misses += prediction->direction_prediction() != record->taken;
        }
        predictor->update(prediction, record->taken, record->target);
    }
    end_trace();
    const unsigned long long instructions = 100000000ULL;
    const double mpki = 1000.0 * static_cast<double>(misses) / instructions;
    if (json) {
        printf("{\"predictor\":\"%s\",\"instructions\":%llu,"
               "\"branches\":%llu,\"conditional_branches\":%llu,"
               "\"direction_misses\":%llu,\"direction_mpki\":%.8f,"
               "\"conditional_miss_rate\":%.10f}\n",
               PREDICTOR_NAME, instructions, branches, conditional, misses,
               mpki, conditional ? static_cast<double>(misses) / conditional : 0.0);
    } else {
        printf("%0.3f MPKI\n", mpki);
    }
    delete predictor;
    return 0;
}
