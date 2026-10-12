CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
HEADERS = predictor.h branch.h trace.h my_predictor.h

.PHONY: all clean test baselines
all: predict
baselines: predict_bimodal predict_gshare

predict: predict.cc trace.cc $(HEADERS)
	$(CXX) $(CXXFLAGS) -o $@ predict.cc trace.cc
predict_bimodal: predict.cc trace.cc $(HEADERS)
	$(CXX) $(CXXFLAGS) -DPREDICTOR_TYPE=bimodal_predictor -DPREDICTOR_NAME='"bimodal"' -o $@ predict.cc trace.cc
predict_gshare: predict.cc trace.cc $(HEADERS)
	$(CXX) $(CXXFLAGS) -DPREDICTOR_TYPE=gshare_predictor -DPREDICTOR_NAME='"gshare"' -o $@ predict.cc trace.cc
predict_extra_credit: predict_extra_credit.cc trace.cc $(HEADERS)
	$(CXX) $(CXXFLAGS) -o $@ predict_extra_credit.cc trace.cc

test:
	$(CXX) $(CXXFLAGS) -Werror -o ../tests/test_predictor ../tests/test_predictor.cc
	../tests/test_predictor

clean:
	rm -f predict predict_bimodal predict_gshare predict_extra_credit ../tests/test_predictor
