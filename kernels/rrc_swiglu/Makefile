# RRC-SwiGLU CUDA Kernel Makefile
# Experimental Ragged RMS-Confidence SwiGLU kernel
# Build with nvcc 12.x targeting CUDA compute capability 7.0+

# Compiler and flags
NVCC := nvcc
NVCCFLAGS := -std=c++17 -O3 --gpu-architecture=sm_70
NVCCFLAGS += -Xcompiler -Wall -Xcompiler -Wextra
NVCCFLAGS += --expt-relaxed-constexpr

# Include paths
INCLUDES := -I.

# Source files
TEST_SRC := rrc_swiglu_test.cu
KERNEL_SRC := rrc_swiglu_kernel.cu

# Output executable
TEST_BIN := rrc_swiglu_test

# Default target
.PHONY: all clean test help

all: $(TEST_BIN)

# Build test executable
$(TEST_BIN): $(TEST_SRC) $(KERNEL_SRC) rrc_swiglu.cuh
	$(NVCC) $(NVCCFLAGS) $(INCLUDES) -o $@ $(TEST_SRC) $(KERNEL_SRC)

# Run tests
run-test: $(TEST_BIN)
	./$(TEST_BIN)

# Run benchmark
run-bench: $(TEST_BIN)
	./$(TEST_BIN) --benchmark

# Run benchmark with custom settings
run-bench-large: $(TEST_BIN)
	./$(TEST_BIN) --benchmark --rows 1024 --max-cols 4096 --iters 100

# Clean build artifacts
clean:
	rm -f $(TEST_BIN) *.o

# Help
help:
	@echo "RRC-SwiGLU CUDA Kernel Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all          - Build the test executable (default)"
	@echo "  run-test     - Build and run correctness tests"
	@echo "  run-bench    - Build and run benchmark"
	@echo "  run-bench-large - Build and run benchmark with large inputs"
	@echo "  clean        - Remove build artifacts"
	@echo "  help         - Show this help"
	@echo ""
	@echo "Build requirements:"
	@echo "  - nvcc 12.x"
	@echo "  - CUDA compute capability 7.0 or newer"
	@echo ""
	@echo "Command-line options for $(TEST_BIN):"
	@echo "  --rows N         Number of ragged rows (default: varies in test)"
	@echo "  --max-cols N     Maximum columns per row (default: varies in test)"
	@echo "  --iters N        Number of benchmark iterations (default: 10)"
	@echo "  --warmup N       Number of warmup iterations (default: 3)"
	@echo "  --eps E          Epsilon for RMS normalization (default: 1e-6)"
	@echo "  --threshold T    Confidence threshold (default: 0.5)"
	@echo "  --sharpness S    Confidence sharpness (default: 10.0)"
	@echo "  --benchmark      Run benchmark mode"
	@echo "  --test           Run correctness tests (default)"
