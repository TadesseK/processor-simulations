#include <iomanip>
#include <iostream>
#include "../src/branch.h"
#include "../src/predictor.h"
#include "../src/my_predictor.h"

int main() {
    pm_predictor predictor;
    const unsigned int addresses[] = {0x140, 0x141, 0x142, 0x146, 0x14f, 0x159, 0x177, 0x129};
    const bool outcomes[] = {true, true, false, true, false, true, false, false};
    std::cout << "step,PC,actual,GHRbefore,hash,set,tag,bmiindex,bmibefore,bmipred,globalhitway,globalbefore,finalpred,bmiafter,way0after,way1after,victimafter,GHRafter\n";
    for (unsigned int i = 0; i < 8; ++i) {
        branch_info branch{addresses[i], OP_JNZ, BR_CONDITIONAL};
        const unsigned int history = predictor.history_value();
        pm_update *update = static_cast<pm_update *>(predictor.predict(branch));
        const unsigned int index = update->bimodal_index;
        const unsigned int set = update->global_index;
        const unsigned int hash = (addresses[i] ^ history) & 32767U;
        const unsigned int bmi = predictor.bimodal_counter(index);
        const int way = update->global_way;
        const int global_counter = way < 0 ? -1 : predictor.global_counter(set, static_cast<unsigned int>(way));
        const bool bmi_prediction = update->bimodal_prediction;
        const bool final_prediction = update->direction_prediction();
        const unsigned int tag = update->global_tag;
        predictor.update(update, outcomes[i], 0);
        std::cout << i + 1 << ",0x" << std::hex << addresses[i] << std::dec
                  << ',' << (outcomes[i] ? "T" : "NT") << ',' << history
                  << ",0x" << std::hex << hash << std::dec
                  << ',' << set << ',' << tag << ',' << index << ',' << bmi
                  << ',' << (bmi_prediction ? "T" : "NT") << ',' << way
                  << ',' << global_counter << ',' << (final_prediction ? "T" : "NT")
                  << ',' << static_cast<unsigned int>(predictor.bimodal_counter(index));
        for (unsigned int w = 0; w < 2; ++w) {
            if (predictor.global_valid(set, w)) {
                std::cout << ",tag=" << predictor.global_tag(set, w)
                          << ":counter=" << static_cast<unsigned int>(predictor.global_counter(set, w));
            } else {
                std::cout << ",invalid";
            }
        }
        std::cout << ',' << predictor.lru_victim(set) << ',' << predictor.history_value() << '\n';
    }
}
