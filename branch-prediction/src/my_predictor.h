#ifndef MY_PREDICTOR_H
#define MY_PREDICTOR_H

#include <cassert>
#include <cstring>

// A prediction retains the indices computed BEFORE the outcome enters the GHR.
class pm_update : public branch_update {
public:
    unsigned int bimodal_index;
    unsigned int global_index;
    unsigned int global_tag;
    int global_way;
    bool bimodal_prediction;
    bool conditional;
};

// The assignment permits two global ways and a GHR XOR instead of PIR/HASH.
// The high hash bits select a set; the low bits form its tag.
// The final two template options exist to replay the small appendix example.
// Production uses unconditional allocation on a global miss and a fresh weak
// counter for the observed direction. The appendix retains the victim counter.
template <unsigned int BIMODAL_BITS, unsigned int GLOBAL_INDEX_BITS,
          unsigned int GLOBAL_TAG_BITS, unsigned int ADDRESS_SHIFT = 0,
          bool ALLOCATE_ON_BIMODAL_MISS = false,
          bool PRESERVE_VICTIM_COUNTER = false>
class hybrid_predictor : public branch_predictor {
public:
    enum {
        HISTORY_BITS = GLOBAL_INDEX_BITS + GLOBAL_TAG_BITS,
        BIMODAL_ENTRIES = 1u << BIMODAL_BITS,
        GLOBAL_SETS = 1u << GLOBAL_INDEX_BITS,
        GLOBAL_WAYS = 2,
        HISTORY_MASK = (1u << HISTORY_BITS) - 1u,
        TAG_MASK = (1u << GLOBAL_TAG_BITS) - 1u
    };

    struct global_entry {
        unsigned int tag;
        unsigned char counter;
        bool valid;
    };

private:
    unsigned char bimodal_[BIMODAL_ENTRIES];
    global_entry global_[GLOBAL_SETS][GLOBAL_WAYS];
    unsigned char lru_[GLOBAL_SETS];
    unsigned int history_;
    pm_update update_;

    static void train(unsigned char &counter, bool taken) {
        if (taken) {
            if (counter < 3) ++counter;
        } else if (counter > 0) {
            --counter;
        }
    }

public:
    hybrid_predictor() {
        static_assert(BIMODAL_BITS > 0 && BIMODAL_BITS < 31,
                      "Invalid bimodal index width");
        static_assert(GLOBAL_INDEX_BITS > 0 && GLOBAL_TAG_BITS > 0 &&
                      HISTORY_BITS < 31 && ADDRESS_SHIFT < 32,
                      "Invalid global predictor configuration");
        reset();
    }

    void reset() {
        history_ = 0;
        for (unsigned int i = 0; i < BIMODAL_ENTRIES; ++i)
            bimodal_[i] = 1; // weakly not taken
        for (unsigned int set = 0; set < GLOBAL_SETS; ++set) {
            lru_[set] = 0;
            for (unsigned int way = 0; way < GLOBAL_WAYS; ++way) {
                global_[set][way].tag = 0;
                global_[set][way].counter = 1;
                global_[set][way].valid = false;
            }
        }
    }

    branch_update *predict(branch_info &branch) {
        update_.conditional = (branch.br_flags & BR_CONDITIONAL) != 0;
        update_.global_way = -1;
        update_.bimodal_index = 0;
        update_.global_index = 0;
        update_.global_tag = 0;
        update_.bimodal_prediction = true;
        update_.direction_prediction(true);
        update_.target_prediction(0); // target prediction is outside scope
        if (!update_.conditional) return &update_;

        const unsigned int address = branch.address >> ADDRESS_SHIFT;
        update_.bimodal_index = address & (BIMODAL_ENTRIES - 1u);
        const unsigned int hash = (address ^ history_) & HISTORY_MASK;
        update_.global_index = hash >> GLOBAL_TAG_BITS;
        update_.global_tag = hash & TAG_MASK;
        update_.bimodal_prediction = bimodal_[update_.bimodal_index] >= 2;
        bool prediction = update_.bimodal_prediction;
        for (unsigned int way = 0; way < GLOBAL_WAYS; ++way) {
            const global_entry &entry = global_[update_.global_index][way];
            if (entry.valid && entry.tag == update_.global_tag) {
                update_.global_way = static_cast<int>(way);
                prediction = entry.counter >= 2;
                break;
            }
        }
        update_.direction_prediction(prediction);
        return &update_;
    }

    void update(branch_update *record, bool taken, unsigned int /* target */) {
        const pm_update &saved = *static_cast<pm_update *>(record);
        if (!saved.conditional) return;

        train(bimodal_[saved.bimodal_index], taken);
        int way = saved.global_way;
        const unsigned int set = saved.global_index;
        if (way < 0 && (!ALLOCATE_ON_BIMODAL_MISS ||
                        saved.bimodal_prediction != taken)) {
            // Fill an invalid way before evicting the least recently used way.
            way = lru_[set];
            for (unsigned int candidate = 0; candidate < GLOBAL_WAYS; ++candidate) {
                if (!global_[set][candidate].valid) {
                    way = static_cast<int>(candidate);
                    break;
                }
            }
            global_entry &entry = global_[set][way];
            entry.valid = true;
            entry.tag = saved.global_tag;
            if (PRESERVE_VICTIM_COUNTER) {
                train(entry.counter, taken);
            } else {
                entry.counter = taken ? 2 : 1;
            }
        } else if (way >= 0) {
            train(global_[set][way].counter, taken);
        }
        if (way >= 0) lru_[set] = static_cast<unsigned char>(way ^ 1);
        history_ = ((history_ << 1) | static_cast<unsigned int>(taken)) & HISTORY_MASK;
    }

    // State accessors make the worked example and focused unit checks reproducible.
    unsigned int history_value() const { return history_; }
    unsigned char bimodal_counter(unsigned int index) const {
        assert(index < BIMODAL_ENTRIES);
        return bimodal_[index];
    }
    bool global_valid(unsigned int set, unsigned int way) const {
        assert(set < GLOBAL_SETS && way < GLOBAL_WAYS);
        return global_[set][way].valid;
    }
    unsigned int global_tag(unsigned int set, unsigned int way) const {
        assert(set < GLOBAL_SETS && way < GLOBAL_WAYS);
        return global_[set][way].tag;
    }
    unsigned char global_counter(unsigned int set, unsigned int way) const {
        assert(set < GLOBAL_SETS && way < GLOBAL_WAYS);
        return global_[set][way].counter;
    }
    unsigned int lru_victim(unsigned int set) const {
        assert(set < GLOBAL_SETS);
        return lru_[set];
    }
    void set_bimodal_counter(unsigned int index, unsigned int value) {
        assert(index < BIMODAL_ENTRIES && value < 4);
        bimodal_[index] = static_cast<unsigned char>(value);
    }
    void set_global_counter(unsigned int set, unsigned int way, unsigned int value) {
        assert(set < GLOBAL_SETS && way < GLOBAL_WAYS && value < 4);
        global_[set][way].counter = static_cast<unsigned char>(value);
    }
};

// Required Pentium M inspired direction predictor: 4096 bimodal counters,
// 512 global sets x 2 ways, six-bit tags, and a 15-bit conditional GHR.
class pm_predictor : public hybrid_predictor<12, 9, 6> {};

// Comparison with the bimodal component in isolation, using identical reset.
class bimodal_predictor : public branch_predictor {
    unsigned char table_[4096];
    pm_update update_;
public:
    bimodal_predictor() {
        for (unsigned int i = 0; i < 4096; ++i) table_[i] = 1;
    }
    branch_update *predict(branch_info &branch) {
        update_.conditional = (branch.br_flags & BR_CONDITIONAL) != 0;
        update_.bimodal_index = branch.address & 4095u;
        update_.direction_prediction(!update_.conditional ||
                                    table_[update_.bimodal_index] >= 2);
        update_.target_prediction(0);
        return &update_;
    }
    void update(branch_update *record, bool taken, unsigned int /* target */) {
        const pm_update &saved = *static_cast<pm_update *>(record);
        if (!saved.conditional) return;
        unsigned char &counter = table_[saved.bimodal_index];
        if (taken) { if (counter < 3) ++counter; }
        else if (counter > 0) --counter;
    }
};

// Original supplied 32768-entry gshare, retained as an independent baseline.
class gshare_update : public branch_update {
public:
    unsigned int index;
};
class gshare_predictor : public branch_predictor {
public:
    enum { HISTORY_LENGTH = 15, TABLE_BITS = 15 };
    gshare_update u;
    branch_info bi;
    unsigned int history;
    unsigned char tab[1 << TABLE_BITS];

    gshare_predictor() : history(0) { memset(tab, 0, sizeof(tab)); }
    branch_update *predict(branch_info &branch) {
        bi = branch;
        if (branch.br_flags & BR_CONDITIONAL) {
            u.index = (history << (TABLE_BITS - HISTORY_LENGTH)) ^
                      (branch.address & ((1 << TABLE_BITS) - 1));
            u.direction_prediction(tab[u.index] >> 1);
        } else {
            u.direction_prediction(true);
        }
        u.target_prediction(0);
        return &u;
    }
    void update(branch_update *record, bool taken, unsigned int /* target */) {
        if (bi.br_flags & BR_CONDITIONAL) {
            unsigned char &counter = tab[static_cast<gshare_update *>(record)->index];
            if (taken) { if (counter < 3) ++counter; }
            else if (counter > 0) --counter;
            history = ((history << 1) | static_cast<unsigned int>(taken)) &
                      ((1 << HISTORY_LENGTH) - 1);
        }
    }
};

// Optional target/loop extra-credit extension was not required or implemented.
// Keeping this explicit stub lets the supplied optional driver still compile.
class cpm_predictor : public branch_predictor {
    branch_update update_;
public:
    branch_update *predict(branch_info &) {
        update_.direction_prediction(true);
        update_.target_prediction(0);
        return &update_;
    }
};

#endif
