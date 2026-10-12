#include <cstdlib>
#include <cstring>
#include <iostream>

#include "../src/branch.h"
#include "../src/predictor.h"
#include "../src/my_predictor.h"
#include "appendix_example.h"

int main() {
    appendix_predictor predictor;
    initialize_appendix(predictor);
    std::cout << "step,branch,pc,actual,ghr_before,bimodal_index,global_set,global_tag,"
                 "bimodal_prediction,global_hit,final_prediction,expected_prediction,correct\n";
    unsigned int step = 0;
    unsigned int mistakes = 0;
    for (const appendix_branch &example : appendix_branches()) {
        ++step;
        branch_info instruction{example.address, OP_JNZ, BR_CONDITIONAL};
        const unsigned int history = predictor.history_value();
        pm_update *update = static_cast<pm_update *>(predictor.predict(instruction));
        const bool prediction = update->direction_prediction();
        const bool correct = prediction == example.taken;
        const char *name = example.address == 0x44 ? "b1" : example.address == 0x6c ? "b2" : "b3";
        std::cout << step << ',' << name << ",0x" << std::hex << example.address << std::dec
                  << ',' << example.taken << ',' << history << ',' << update->bimodal_index
                  << ',' << update->global_index << ',' << update->global_tag
                  << ',' << update->bimodal_prediction << ',' << (update->global_way >= 0)
                  << ',' << prediction << ',' << example.final_prediction << ',' << correct << '\n';
        if (prediction != example.final_prediction || history != example.history ||
            update->global_index != example.set || update->global_tag != example.tag ||
            update->bimodal_prediction != example.bimodal_prediction ||
            (update->global_way >= 0) != example.global_hit) {
            std::cerr << "Appendix mismatch at step " << step << '\n';
            return EXIT_FAILURE;
        }
        mistakes += !correct;
        predictor.update(update, example.taken, 0);
    }
    std::cerr << "Appendix B: " << step << " matching rows, " << mistakes
              << " mistakes, " << (step - mistakes) << " correct predictions\n";
    return EXIT_SUCCESS;
}
