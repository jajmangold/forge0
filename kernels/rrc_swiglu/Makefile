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
CUDA_IMAGE := nvidia/cuda@sha256:020bc241a628776338f4d4053fed4c38f6f7f3d7eb5919fecb8de313bb8ba47c
GPU ?= 0

# Default target
.PHONY: all clean run-test run-bench run-bench-large run-pinned-cuda help

all: $(TEST_BIN)

# Build test executable
$(TEST_BIN): $(TEST_SRC) $(KERNEL_SRC) rrc_swiglu.cuh
	$(NVCC) $(NVCCFLAGS) $(INCLUDES) -o $@ $(TEST_SRC) $(KERNEL_SRC)

# Run tests
run-test: $(TEST_BIN)
	./$(TEST_BIN) --iterations 10

# Run benchmark
run-bench: $(TEST_BIN)
	./$(TEST_BIN) --iterations 100

# Run benchmark with custom settings
run-bench-large: $(TEST_BIN)
	./$(TEST_BIN) --num_rows 8192 --max_row_len 2048 --iterations 200

# Reproduce correctness boundaries and the reference benchmark in the locked
# CUDA 12.9.1 toolchain. Override GPU=<index> to select a device.
run-pinned-cuda:
	docker run --rm --gpus "device=$(GPU)" -v "$(CURDIR):/workspace" -w /workspace \
		$(CUDA_IMAGE) bash -lc 'make clean all && \
		for block in 32 256 1024; do \
			./$(TEST_BIN) --num_rows 128 --max_row_len 2048 --iterations 10 --block_size $$block; \
		done && \
		./$(TEST_BIN) --num_rows 128 --max_row_len 2048 --iterations 100 --block_size 256'

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
	@echo "  run-pinned-cuda - Reproduce tests/benchmark in a digest-pinned CUDA image"
	@echo "  clean        - Remove build artifacts"
	@echo "  help         - Show this help"
	@echo ""
	@echo "Build requirements:"
	@echo "  - nvcc 12.x"
	@echo "  - CUDA compute capability 7.0 or newer"
	@echo ""
	@echo "Command-line options for $(TEST_BIN):"
	@echo "  --num_rows N     Number of ragged rows (default: 128)"
	@echo "  --max_row_len N  Maximum and explicitly tested row length (default: 1024)"
	@echo "  --iterations N   Number of benchmark iterations (default: 100)"
	@echo "  --epsilon E      RMS epsilon (default: 1e-5)"
	@echo "  --threshold T    Confidence threshold (default: 0.5)"
	@echo "  --sharpness S    Confidence sharpness (default: 10.0)"
	@echo "  --block_size N   Threads per block; multiple of 32, 32..1024 (default: 256)"
	@echo "  --abs_tol E      Absolute correctness tolerance (default: 1e-4)"
	@echo "  --rel_tol E      Relative correctness tolerance (default: 1e-3)"
