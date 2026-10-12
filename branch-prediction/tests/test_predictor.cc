#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

#include "../src/branch.h"
#include "../src/predictor.h"
#include "../src/my_predictor.h"
#include "appendix_example.h"

namespace {

unsigned int checks = 0;

void require(bool condition, const std::string &message) {
    ++checks;
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(EXIT_FAILURE);
    }
}

using small_predictor = hybrid_predictor<4, 2, 2, 0, false, false>;

branch_info branch(unsigned int address, unsigned int flags = BR_CONDITIONAL) {
    return branch_info{address, OP_JNZ, flags};
}

template <typename Predictor>
pm_update *predict_key(Predictor &predictor, unsigned int set, unsigned int tag) {
    // With two index and two tag bits, select the requested global key using
    // the current history. This allows repeated visits to one tagged entry.
    branch_info instruction = branch(((set << 2) | tag) ^ predictor.history_value());
    return static_cast<pm_update *>(predictor.predict(instruction));
}

template <typename Predictor>
void visit_key(Predictor &predictor, unsigned int set, unsigned int tag, bool taken) {
    pm_update *update = predict_key(predictor, set, tag);
    predictor.update(update, taken, 0);
}

template <typename Predictor>
std::vector<unsigned int> state(const Predictor &predictor) {
    std::vector<unsigned int> result{predictor.history_value()};
    for (unsigned int index = 0; index < 16; ++index) {
        result.push_back(predictor.bimodal_counter(index));
    }
    for (unsigned int set = 0; set < 4; ++set) {
        result.push_back(predictor.lru_victim(set));
        for (unsigned int way = 0; way < 2; ++way) {
            result.push_back(predictor.global_valid(set, way));
            result.push_back(predictor.global_tag(set, way));
            result.push_back(predictor.global_counter(set, way));
        }
    }
    return result;
}

void counter_saturation() {
    small_predictor predictor;
    branch_info instruction = branch(3);
    for (unsigned int i = 0; i < 10; ++i) {
        predictor.update(predictor.predict(instruction), true, 0);
    }
    require(predictor.bimodal_counter(3) == 3, "bimodal increments saturate at 3");
    for (unsigned int i = 0; i < 10; ++i) {
        predictor.update(predictor.predict(instruction), false, 0);
    }
    require(predictor.bimodal_counter(3) == 0, "bimodal decrements saturate at 0");

    predictor.reset();
    visit_key(predictor, 1, 2, true);
    require(predictor.global_counter(1, 0) == 2, "taken allocation starts weak taken");
    for (unsigned int i = 0; i < 10; ++i) {
        pm_update *update = predict_key(predictor, 1, 2);
        require(update->global_way == 0, "saturation visits hit the allocated entry");
        predictor.update(update, true, 0);
    }
    require(predictor.global_counter(1, 0) == 3, "global increments saturate at 3");
    for (unsigned int i = 0; i < 10; ++i) {
        visit_key(predictor, 1, 2, false);
    }
    require(predictor.global_counter(1, 0) == 0, "global decrements saturate at 0");
    predictor.reset();
    visit_key(predictor, 1, 2, false);
    require(predictor.global_counter(1, 0) == 1, "not-taken allocation starts weak not taken");
}

void fallback_and_global_priority() {
    small_predictor predictor;
    predictor.set_bimodal_counter(7, 0);
    branch_info instruction = branch(7);
    pm_update *update = static_cast<pm_update *>(predictor.predict(instruction));
    require(update->global_way == -1, "cold lookup misses global table");
    require(!update->direction_prediction(), "global miss uses not-taken bimodal prediction");
    predictor.update(update, true, 0);

    unsigned int pc = 7 ^ predictor.history_value();
    predictor.set_bimodal_counter(pc & 15, 0);
    update = predict_key(predictor, 1, 3);
    require(update->global_way == 0, "repeated tagged context hits");
    require(!update->bimodal_prediction, "bimodal predicts not taken for disagreement");
    require(update->direction_prediction(), "taken global hit overrides not-taken bimodal");
    predictor.update(update, true, 0);

    predictor.set_global_counter(1, 0, 0);
    pc = 7 ^ predictor.history_value();
    predictor.set_bimodal_counter(pc & 15, 3);
    update = predict_key(predictor, 1, 3);
    require(update->bimodal_prediction, "bimodal predicts taken for reverse disagreement");
    require(!update->direction_prediction(), "not-taken global hit overrides taken bimodal");
    predictor.update(update, false, 0);

    predictor.reset();
    predictor.set_bimodal_counter(0, 3);
    instruction = branch(0);
    update = static_cast<pm_update *>(predictor.predict(instruction));
    require(update->global_way == -1, "invalid zero-tag entry cannot hit");
    require(update->direction_prediction(), "global miss also falls back to taken bimodal");
    predictor.update(update, true, 0);
}

void valid_tags_and_replacement() {
    small_predictor predictor;
    visit_key(predictor, 2, 0, true);
    require(predictor.global_valid(2, 0), "first allocation makes way 0 valid");
    require(!predictor.global_valid(2, 1), "first allocation preserves invalid way 1");
    require(predictor.lru_victim(2) == 1, "first allocation makes other way the victim");

    pm_update *update = predict_key(predictor, 2, 1);
    require(update->global_way == -1, "same set with a different tag misses");
    predictor.update(update, false, 0);
    require(predictor.global_tag(2, 0) == 0, "invalid-first allocation preserves valid tag");
    require(predictor.global_valid(2, 1) && predictor.global_tag(2, 1) == 1,
            "second miss fills invalid way 1");
    require(predictor.lru_victim(2) == 0, "second allocation makes way 0 the victim");

    update = predict_key(predictor, 2, 0);
    require(update->global_way == 0, "existing tag hits its own way");
    predictor.update(update, true, 0);
    require(predictor.lru_victim(2) == 1, "hit updates two-way LRU recency");
    visit_key(predictor, 2, 2, false);
    require(predictor.global_tag(2, 0) == 0 && predictor.global_tag(2, 1) == 2,
            "full set replaces the least recently used way 1");
    require(predictor.lru_victim(2) == 0, "replacement marks way 0 least recent");
    visit_key(predictor, 2, 3, true);
    require(predictor.global_tag(2, 0) == 3 && predictor.global_tag(2, 1) == 2,
            "next replacement deterministically evicts way 0");
    for (unsigned int set = 0; set < 4; ++set) {
        if (set != 2) {
            require(!predictor.global_valid(set, 0) && !predictor.global_valid(set, 1),
                    "replacement does not change an unrelated set");
        }
    }
}

void prediction_time_history() {
    small_predictor predictor;
    branch_info instruction = branch(4);
    pm_update *update = static_cast<pm_update *>(predictor.predict(instruction));
    require(update->bimodal_index == 4 && update->global_index == 1 && update->global_tag == 0,
            "prediction records indices and tag from old history");
    predictor.update(update, true, 0);
    require(predictor.history_value() == 1, "conditional update shifts in actual taken outcome");
    require(predictor.global_valid(1, 0) && predictor.global_tag(1, 0) == 0,
            "allocation uses prediction-time tag, not post-update tag 1");
    require(predictor.bimodal_counter(4) == 2, "bimodal updates exactly the prediction-time entry");

    for (unsigned int i = 0; i < 10; ++i) {
        predictor.update(predictor.predict(instruction), true, 0);
    }
    require(predictor.history_value() == 15, "history is masked to index-plus-tag width");
    predictor.update(predictor.predict(instruction), false, 0);
    require(predictor.history_value() == 14, "history retains newest four actual outcomes");
}

void unconditional_leaves_state_unchanged() {
    small_predictor predictor;
    visit_key(predictor, 0, 1, true);
    visit_key(predictor, 3, 2, false);
    visit_key(predictor, 0, 3, true);
    const std::vector<unsigned int> before = state(predictor);
    for (unsigned int flags : {0U, static_cast<unsigned int>(BR_CALL),
                               static_cast<unsigned int>(BR_RETURN),
                               static_cast<unsigned int>(BR_INDIRECT)}) {
        branch_info instruction = branch(0xdeadbeefU, flags);
        pm_update *update = static_cast<pm_update *>(predictor.predict(instruction));
        require(!update->conditional, "unconditional branch is marked nonconditional");
        require(update->direction_prediction(), "unconditional branch predicts taken");
        require(state(predictor) == before, "unconditional prediction does not mutate tables or history");
        predictor.update(update, true, 0x1234U);
        require(state(predictor) == before, "unconditional update does not mutate tables or history");
    }
}

void allocation_policy() {
    hybrid_predictor<4, 2, 2, 0, true, false> selective;
    pm_update *update = predict_key(selective, 1, 1);
    require(!update->bimodal_prediction, "cold weak-not-taken counter predicts not taken");
    selective.update(update, false, 0);
    require(!selective.global_valid(1, 0) && !selective.global_valid(1, 1),
            "optional selective mode does not allocate a correct bimodal miss");
    update = predict_key(selective, 1, 1);
    selective.update(update, true, 0);
    require(selective.global_valid(1, 0), "optional selective mode allocates on bimodal error");

    small_predictor always;
    visit_key(always, 1, 1, false);
    require(always.global_valid(1, 0), "production policy allocates even after correct bimodal miss");
}

std::vector<bool> exercise(small_predictor &predictor) {
    std::vector<bool> predictions;
    for (unsigned int i = 0; i < 80; ++i) {
        branch_info instruction = branch((i * 13U + 5U) & 31U);
        branch_update *update = predictor.predict(instruction);
        predictions.push_back(update->direction_prediction());
        predictor.update(update, (i % 5U) < 3U, 0);
    }
    return predictions;
}

void reset_is_deterministic() {
    small_predictor predictor;
    const std::vector<bool> first = exercise(predictor);
    const std::vector<unsigned int> first_state = state(predictor);
    predictor.reset();
    require(predictor.history_value() == 0, "reset clears history");
    for (unsigned int index = 0; index < 16; ++index) {
        require(predictor.bimodal_counter(index) == 1, "reset restores weak-not-taken bimodal counter");
    }
    for (unsigned int set = 0; set < 4; ++set) {
        require(predictor.lru_victim(set) == 0, "reset restores deterministic victim");
        for (unsigned int way = 0; way < 2; ++way) {
            require(!predictor.global_valid(set, way), "reset invalidates global entries");
            require(predictor.global_counter(set, way) == 1, "reset restores global counter");
        }
    }
    require(exercise(predictor) == first, "reset replays identical predictions");
    require(state(predictor) == first_state, "reset replay produces identical complete state");
}

void appendix_example() {
    appendix_predictor predictor;
    initialize_appendix(predictor);
    unsigned int row = 0;
    unsigned int mistakes = 0;
    for (const appendix_branch &example : appendix_branches()) {
        ++row;
        const std::string context = "appendix row " + std::to_string(row) + ": ";
        branch_info instruction = branch(example.address);
        require(predictor.history_value() == example.history, context + "history matches");
        pm_update *update = static_cast<pm_update *>(predictor.predict(instruction));
        require(update->global_index == example.set && update->global_tag == example.tag,
                context + "row and tag match");
        require(update->bimodal_prediction == example.bimodal_prediction,
                context + "bimodal prediction matches");
        require((update->global_way >= 0) == example.global_hit, context + "global hit matches");
        require(update->direction_prediction() == example.final_prediction,
                context + "final prediction matches");
        mistakes += update->direction_prediction() != example.taken;
        predictor.update(update, example.taken, 0);
    }
    require(row == 22, "appendix exercises all 22 result-table rows");
    require(mistakes == 9, "appendix trace has nine direction mistakes");
}

} // namespace

int main() {
    counter_saturation();
    fallback_and_global_priority();
    valid_tags_and_replacement();
    prediction_time_history();
    unconditional_leaves_state_unchanged();
    allocation_policy();
    reset_is_deterministic();
    appendix_example();
    std::cout << "PASS: 8 test groups, " << checks << " checks\n";
    return EXIT_SUCCESS;
}
