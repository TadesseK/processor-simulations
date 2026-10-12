#ifndef APPENDIX_EXAMPLE_H
#define APPENDIX_EXAMPLE_H

#include <array>
#include <cstdint>

// Appendix B uses shifted addresses, 16 bimodal counters, and four
// two-way global sets. Its illustrative counters begin in different states.
using appendix_predictor = hybrid_predictor<4, 2, 2, 2, false, true>;

struct appendix_branch {
    unsigned int address;
    bool taken;
    unsigned int history;
    unsigned int set;
    unsigned int tag;
    bool bimodal_prediction;
    bool global_hit;
    bool final_prediction;
};

inline const std::array<appendix_branch, 22> &appendix_branches() {
    // Expected values come from the handout's Hybrid Predictor Results table.
    // Row 5 predicts NT from the local counter; the separate global table's
    // printed T is inconsistent with that table. Row 22's final prediction
    // is T, despite the separate global table printing NT on a miss.
    static const std::array<appendix_branch, 22> trace{{
        {0x44, true,  0x0, 0, 1, false, false, false},
        {0x90, true,  0x1, 1, 1, false, false, false},
        {0x44, false, 0x3, 0, 2, true,  false, true },
        {0x6c, false, 0x6, 3, 1, true,  false, true },
        {0x90, true,  0xc, 2, 0, false, false, false},
        {0x44, true,  0x9, 2, 0, false, true,  true },
        {0x90, true,  0x3, 1, 3, true,  false, true },
        {0x44, false, 0x7, 1, 2, true,  false, true },
        {0x6c, false, 0xe, 1, 1, true,  false, true },
        {0x90, true,  0xc, 2, 0, true,  true,  true },
        {0x44, false, 0x9, 2, 0, false, true,  true },
        {0x6c, true,  0x2, 2, 1, false, false, false},
        {0x44, false, 0x5, 1, 0, false, false, false},
        {0x6c, false, 0xa, 0, 1, true,  true,  false},
        {0x90, true,  0x4, 0, 0, true,  false, true },
        {0x44, true,  0x9, 2, 0, false, true,  true },
        {0x90, true,  0x3, 1, 3, true,  false, true },
        {0x44, false, 0x7, 1, 2, false, false, false},
        {0x6c, false, 0xe, 1, 1, false, false, false},
        {0x90, true,  0xc, 2, 0, true,  true,  true },
        {0x44, true,  0x9, 2, 0, false, true,  true },
        {0x90, true,  0x3, 1, 3, true,  false, true }
    }};
    return trace;
}

inline void initialize_appendix(appendix_predictor &predictor) {
    predictor.reset();
    for (unsigned int index = 0; index < 16; ++index) {
        predictor.set_bimodal_counter(index, index % 4);
    }
    for (unsigned int set = 0; set < 4; ++set) {
        predictor.set_global_counter(set, 0, set);
        predictor.set_global_counter(set, 1, 3 - set);
    }
}

#endif
