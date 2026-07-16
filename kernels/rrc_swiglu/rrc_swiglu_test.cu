// RRC-SwiGLU Test and Benchmark Executable
// Tests correctness and benchmarks the fused kernel against an unfused baseline.

/*
 * Mathematical Operation (for element i in row r):
 *   Let x_i be the input, gate_i and up_i be SwiGLU weights, residual_i be the residual.
 *   RMS normalization: n_i = x_i / sqrt(mean(x^2) + eps)
 *   Confidence: c_i = sigmoid(sharpness * (|n_i| - threshold))
 *   SwiGLU activation: swiglu_i = silu(gate_i) * up_i
 *   Output: out_i = residual_i + c_i * swiglu_i + (1 - c_i) * n_i
 *
 * Launch strategy: One cooperative block per ragged row, grid-stride element handling.
 * Numerical stability: Sigmoid and SILU computed in stable forms, shared-memory reduction.
 * Novelty scope: Experimental composition of techniques; not an unsupported research claim.
 * Numerical limits: eps > 0, threshold and sharpness finite; inputs should be within representable range.
 * Build: make
 * Run: ./rrc_swiglu_test [options]
 * Sample output: Illustrative until measured on real hardware.
 */

#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>
#include <chrono>
#include <random>
#include <cassert>
#include <limits>
#include <getopt.h>

// Include the kernel header
#include "rrc_swiglu.cuh"

// -----------------------------------------------------------------------------
// CPU double-precision reference implementation
// -----------------------------------------------------------------------------
static void cpu_reference(
    const float* x,
    const float* gate,
    const float* up,
    const float* residual,
    float* out,
    int row_len,
    float eps,
    float threshold,
    float sharpness
) {
    if (row_len == 0) return;

    // Compute mean of squares
    double sum_sq = 0.0;
    for (int i = 0; i < row_len; ++i) {
        double val = static_cast<double>(x[i]);
        sum_sq += val * val;
    }
    double mean_sq = sum_sq / static_cast<double>(row_len);
    double rms = sqrt(mean_sq + static_cast<double>(eps));
    double inv_rms = 1.0 / rms;

    for (int i = 0; i < row_len; ++i) {
        double xi = static_cast<double>(x[i]);
        double n = xi * inv_rms;
        double abs_n = fabs(n);
        double c = 1.0 / (1.0 + exp(-sharpness * (abs_n - threshold)));
        double gate_i = static_cast<double>(gate[i]);
        double up_i = static_cast<double>(up[i]);
        double silu_gate = gate_i / (1.0 + exp(-gate_i));
        double swiglu = silu_gate * up_i;
        double res_i = static_cast<double>(residual[i]);
        double result = res_i + c * swiglu + (1.0 - c) * n;
        out[i] = static_cast<float>(result);
    }
}

// -----------------------------------------------------------------------------
// Unfused two-pass CUDA baseline kernel (simplified)
// -----------------------------------------------------------------------------
// Pass 1: Compute RMS for each row
__global__ void baseline_rms_kernel(
    const float* __restrict__ x,
    float* __restrict__ rms_vals,
    const int* __restrict__ row_offsets,
    int num_rows,
    float eps
) {
    int row = blockIdx.x;
    if (row >= num_rows) return;

    int start = row_offsets[row];
    int end = row_offsets[row + 1];
    int len = end - start;
    if (len <= 0) return;

    extern __shared__ float sdata[];
    float sum_sq = 0.0f;
    for (int i = threadIdx.x; i < len; i += blockDim.x) {
        float val = x[start + i];
        sum_sq += val * val;
    }
    sdata[threadIdx.x] = sum_sq;
    __syncthreads();

    // Block reduction
    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (threadIdx.x < s) {
            sdata[threadIdx.x] += sdata[threadIdx.x + s];
        }
        __syncthreads();
    }
    if (threadIdx.x == 0) {
        rms_vals[row] = sqrtf(sdata[0] / len + eps);
    }
}

// Pass 2: Apply normalization, confidence, SwiGLU, residual
__global__ void baseline_apply_kernel(
    const float* __restrict__ x,
    const float* __restrict__ gate,
    const float* __restrict__ up,
    const float* __restrict__ residual,
    float* __restrict__ out,
    const float* __restrict__ rms_vals,
    const int* __restrict__ row_offsets,
    int num_rows,
    float threshold,
    float sharpness
) {
    int row = blockIdx.x;
    if (row >= num_rows) return;

    int start = row_offsets[row];
    int end = row_offsets[row + 1];
    int len = end - start;
    if (len <= 0) return;

    float inv_rms = 1.0f / rms_vals[row];
    for (int i = threadIdx.x; i < len; i += blockDim.x) {
        float xi = x[start + i];
        float n = xi * inv_rms;
        float abs_n = fabsf(n);
        float c = __frcp_rn(1.0f + __expf(-sharpness * (abs_n - threshold)));
        float gate_i = gate[start + i];
        float up_i = up[start + i];
        float silu_gate = gate_i * __frcp_rn(1.0f + __expf(-gate_i));
        float swiglu = silu_gate * up_i;
        float res_i = residual[start + i];
        out[start + i] = res_i + c * swiglu + (1.0f - c) * n;
    }
}

// -----------------------------------------------------------------------------
// Helper: CUDA error check
// -----------------------------------------------------------------------------
#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            fprintf(stderr, "CUDA error at %s:%d: %s\n", __FILE__, __LINE__, cudaGetErrorString(err)); \
            exit(EXIT_FAILURE); \
        } \
    } while (0)

// -----------------------------------------------------------------------------
// Helper: Generate deterministic ragged row offsets
// -----------------------------------------------------------------------------
std::vector<int> generate_ragged_offsets(
    int num_rows,
    const std::vector<int>& pattern,
    int* total_elements_out
) {
    std::vector<int> offsets(num_rows + 1);
    offsets[0] = 0;
    for (int r = 0; r < num_rows; ++r) {
        int len = pattern[r % pattern.size()];
        offsets[r + 1] = offsets[r] + len;
    }
    *total_elements_out = offsets[num_rows];
    return offsets;
}

// -----------------------------------------------------------------------------
// Validation: Check for NaN/Inf and tolerance
// -----------------------------------------------------------------------------
bool validate_results(
    const float* ref,
    const float* test,
    int n,
    float abs_tol,
    float rel_tol,
    float* max_abs_err_out,
    float* max_rel_err_out
) {
    float max_abs_err = 0.0f;
    float max_rel_err = 0.0f;
    bool valid = true;
    for (int i = 0; i < n; ++i) {
        float a = ref[i];
        float b = test[i];
        if (std::isnan(a) || std::isinf(a) || std::isnan(b) || std::isinf(b)) {
            fprintf(stderr, "  NaN/Inf detected at index %d: ref=%f, test=%f\n", i, a, b);
            valid = false;
            continue;
        }
        float abs_err = fabsf(a - b);
        float rel_err = abs_err / fmaxf(1e-6f, fabsf(a));
        max_abs_err = fmaxf(max_abs_err, abs_err);
        max_rel_err = fmaxf(max_rel_err, rel_err);
        if (abs_err > abs_tol && rel_err > rel_tol) {
            // Mark failure but continue to find all violations
            valid = false;
        }
    }
    if (max_abs_err_out) *max_abs_err_out = max_abs_err;
    if (max_rel_err_out) *max_rel_err_out = max_rel_err;
    return valid;
}

// -----------------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------------
int main(int argc, char* argv[]) {
    // Default parameters
    int num_rows = 128;
    int max_row_len = 1024;
    int iterations = 100;
    float eps = 1e-5f;
    float threshold = 0.5f;
    float sharpness = 10.0f;
    int block_size = 256;
    float abs_tol = 1e-4f;
    float rel_tol = 1e-3f;

    // Parse command-line flags
    static struct option long_options[] = {
        {"num_rows",     required_argument, nullptr, 'r'},
        {"max_row_len",  required_argument, nullptr, 'l'},
        {"iterations",   required_argument, nullptr, 'i'},
        {"epsilon",      required_argument, nullptr, 'e'},
        {"threshold",    required_argument, nullptr, 't'},
        {"sharpness",    required_argument, nullptr, 's'},
        {"block_size",   required_argument, nullptr, 'b'},
        {"abs_tol",      required_argument, nullptr, 'a'},
        {"rel_tol",      required_argument, nullptr, 'R'},
        {"help",         no_argument,       nullptr, 'h'},
        {nullptr, 0, nullptr, 0}
    };

    int opt;
    while ((opt = getopt_long(argc, argv, "r:l:i:e:t:s:b:a:R:h", long_options, nullptr)) != -1) {
        switch (opt) {
            case 'r': num_rows = atoi(optarg); break;
            case 'l': max_row_len = atoi(optarg); break;
            case 'i': iterations = atoi(optarg); break;
            case 'e': eps = atof(optarg); break;
            case 't': threshold = atof(optarg); break;
            case 's': sharpness = atof(optarg); break;
            case 'b': block_size = atoi(optarg); break;
            case 'a': abs_tol = atof(optarg); break;
            case 'R': rel_tol = atof(optarg); break;
            case 'h':
                printf("Usage: %s [options]\n", argv[0]);
                printf("  -r, --num_rows     Number of rows (default: %d)\n", num_rows);
                printf("  -l, --max_row_len  Max row length (default: %d)\n", max_row_len);
                printf("  -i, --iterations   Benchmark iterations (default: %d)\n", iterations);
                printf("  -e, --epsilon      RMS epsilon (default: %e)\n", eps);
                printf("  -t, --threshold    Confidence threshold (default: %f)\n", threshold);
                printf("  -s, --sharpness    Confidence sharpness (default: %f)\n", sharpness);
                printf("  -b, --block_size   CUDA block size (default: %d)\n", block_size);
                printf("  -a, --abs_tol      Absolute tolerance (default: %e)\n", abs_tol);
                printf("  -R, --rel_tol      Relative tolerance (default: %e)\n", rel_tol);
                return 0;
            default:
                fprintf(stderr, "Unknown option. Use -h for help.\n");
                return 1;
        }
    }

    // Validation
    if (num_rows <= 0 || max_row_len <= 0 || iterations <= 0) {
        fprintf(stderr, "Error: num_rows, max_row_len, iterations must be positive.\n");
        return 1;
    }
    if (static_cast<long long>(num_rows) * max_row_len > std::numeric_limits<int>::max()) {
        fprintf(stderr, "Error: requested shape exceeds 32-bit row-offset capacity.\n");
        return 1;
    }
    if (!std::isfinite(eps) || eps <= 0.0f || !std::isfinite(threshold) ||
        !std::isfinite(sharpness) || !std::isfinite(abs_tol) || !std::isfinite(rel_tol) ||
        abs_tol < 0.0f || rel_tol < 0.0f) {
        fprintf(stderr, "Error: floating-point parameters must be finite, epsilon positive, and tolerances nonnegative.\n");
        return 1;
    }
    if (block_size < 32 || block_size > 1024 || block_size % 32 != 0) {
        fprintf(stderr, "Error: block_size must be a multiple of 32 between 32 and 1024.\n");
        return 1;
    }

    printf("RRC-SwiGLU Test and Benchmark\n");
    printf("Parameters: rows=%d, max_row_len=%d, eps=%e, threshold=%f, sharpness=%f\n",
           num_rows, max_row_len, eps, threshold, sharpness);
    printf("Tolerances: abs=%e, rel=%e\n", abs_tol, rel_tol);

    // Deterministic pattern for ragged rows (covers empty, 1, odd, non-warp-multiple, large)
    // Includes empty, singleton, odd, warp-boundary, and greater-than-block rows.
    std::vector<int> pattern = {0, 1, 3, 31, 32, 33, 127, 128, 255, 256, 511, max_row_len};
    for (int& len : pattern) {
        len = std::min(len, max_row_len);
    }

    int total_elements;
    std::vector<int> h_offsets = generate_ragged_offsets(num_rows, pattern, &total_elements);
    printf("Total elements: %d\n", total_elements);

    if (total_elements == 0) {
        printf("All rows are empty. Nothing to compute.\n");
        return 0;
    }

    // Host memory allocation
    std::vector<float> h_x(total_elements);
    std::vector<float> h_gate(total_elements);
    std::vector<float> h_up(total_elements);
    std::vector<float> h_residual(total_elements);
    std::vector<float> h_out_ref(total_elements);
    std::vector<float> h_out_fused(total_elements);
    std::vector<float> h_out_baseline(total_elements);

    // Initialize inputs with deterministic pseudo-random values
    std::mt19937 rng(42);
    std::uniform_real_distribution<float> dist(-1.0f, 1.0f);
    for (int i = 0; i < total_elements; ++i) {
        h_x[i] = dist(rng);
        h_gate[i] = dist(rng);
        h_up[i] = dist(rng);
        h_residual[i] = dist(rng);
    }

    // Compute CPU reference
    printf("Computing CPU reference...\n");
    for (int r = 0; r < num_rows; ++r) {
        int start = h_offsets[r];
        int len = h_offsets[r + 1] - start;
        cpu_reference(
            &h_x[start], &h_gate[start], &h_up[start], &h_residual[start],
            &h_out_ref[start], len, eps, threshold, sharpness
        );
    }

    // Allocate device memory
    float *d_x, *d_gate, *d_up, *d_residual, *d_out;
    int *d_offsets;
    float *d_rms_vals; // for baseline

    CUDA_CHECK(cudaMalloc(&d_x, total_elements * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_gate, total_elements * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_up, total_elements * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_residual, total_elements * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_out, total_elements * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_offsets, (num_rows + 1) * sizeof(int)));
    CUDA_CHECK(cudaMalloc(&d_rms_vals, num_rows * sizeof(float)));

    // Copy to device
    CUDA_CHECK(cudaMemcpy(d_x, h_x.data(), total_elements * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_gate, h_gate.data(), total_elements * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_up, h_up.data(), total_elements * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_residual, h_residual.data(), total_elements * sizeof(float), cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_offsets, h_offsets.data(), (num_rows + 1) * sizeof(int), cudaMemcpyHostToDevice));

    // ---------------------------------------------------------------------
    // Correctness test: Fused kernel
    // ---------------------------------------------------------------------
    printf("\n=== Correctness Test (Fused Kernel) ===\n");
    CUDA_CHECK(cudaMemset(d_out, 0, total_elements * sizeof(float)));
    CUDA_CHECK(launch_rrc_swiglu(
        d_x, d_gate, d_up, d_residual, d_out,
        d_offsets, num_rows, eps, threshold, sharpness, block_size
    ));
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(h_out_fused.data(), d_out, total_elements * sizeof(float), cudaMemcpyDeviceToHost));

    float max_abs_err_fused, max_rel_err_fused;
    bool fused_ok = validate_results(
        h_out_ref.data(), h_out_fused.data(), total_elements,
        abs_tol, rel_tol, &max_abs_err_fused, &max_rel_err_fused
    );
    printf("Fused kernel: %s\n", fused_ok ? "PASS" : "FAIL");
    printf("  Max absolute error: %e\n", max_abs_err_fused);
    printf("  Max relative error: %e\n", max_rel_err_fused);

    // ---------------------------------------------------------------------
    // Correctness test: Baseline (unfused two-pass)
    // ---------------------------------------------------------------------
    printf("\n=== Correctness Test (Baseline) ===\n");
    CUDA_CHECK(cudaMemset(d_out, 0, total_elements * sizeof(float)));
    // Pass 1
    baseline_rms_kernel<<<num_rows, block_size, block_size * sizeof(float)>>>(
        d_x, d_rms_vals, d_offsets, num_rows, eps
    );
    CUDA_CHECK(cudaGetLastError());
    // Pass 2
    baseline_apply_kernel<<<num_rows, block_size>>>(
        d_x, d_gate, d_up, d_residual, d_out,
        d_rms_vals, d_offsets, num_rows, threshold, sharpness
    );
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(h_out_baseline.data(), d_out, total_elements * sizeof(float), cudaMemcpyDeviceToHost));

    float max_abs_err_base, max_rel_err_base;
    bool baseline_ok = validate_results(
        h_out_ref.data(), h_out_baseline.data(), total_elements,
        abs_tol, rel_tol, &max_abs_err_base, &max_rel_err_base
    );
    printf("Baseline kernel: %s\n", baseline_ok ? "PASS" : "FAIL");
    printf("  Max absolute error: %e\n", max_abs_err_base);
    printf("  Max relative error: %e\n", max_rel_err_base);

    if (!fused_ok || !baseline_ok) {
        fprintf(stderr, "\nCorrectness test FAILED. Exiting.\n");
        // Free resources
        cudaFree(d_x);
        cudaFree(d_gate);
        cudaFree(d_up);
        cudaFree(d_residual);
        cudaFree(d_out);
        cudaFree(d_offsets);
        cudaFree(d_rms_vals);
        return 1;
    }

    // ---------------------------------------------------------------------
    // Benchmark
    // ---------------------------------------------------------------------
    printf("\n=== Benchmark (iterations=%d) ===\n", iterations);

    // Warmup
    const int warmup = 10;
    printf("Warming up...\n");
    for (int i = 0; i < warmup; ++i) {
        CUDA_CHECK(launch_rrc_swiglu(
            d_x, d_gate, d_up, d_residual, d_out,
            d_offsets, num_rows, eps, threshold, sharpness, block_size
        ));
    }
    CUDA_CHECK(cudaDeviceSynchronize());

    // Benchmark fused kernel
    cudaEvent_t start_event, stop_event;
    CUDA_CHECK(cudaEventCreate(&start_event));
    CUDA_CHECK(cudaEventCreate(&stop_event));

    printf("Benchmarking fused kernel...\n");
    CUDA_CHECK(cudaEventRecord(start_event));
    for (int i = 0; i < iterations; ++i) {
        CUDA_CHECK(launch_rrc_swiglu(
            d_x, d_gate, d_up, d_residual, d_out,
            d_offsets, num_rows, eps, threshold, sharpness, block_size
        ));
    }
    CUDA_CHECK(cudaEventRecord(stop_event));
    CUDA_CHECK(cudaEventSynchronize(stop_event));
    float fused_time_ms = 0.0f;
    CUDA_CHECK(cudaEventElapsedTime(&fused_time_ms, start_event, stop_event));
    float fused_avg_ms = fused_time_ms / iterations;

    // Benchmark baseline kernel
    printf("Benchmarking baseline kernel...\n");
    CUDA_CHECK(cudaEventRecord(start_event));
    for (int i = 0; i < iterations; ++i) {
        baseline_rms_kernel<<<num_rows, block_size, block_size * sizeof(float)>>>(
            d_x, d_rms_vals, d_offsets, num_rows, eps
        );
        baseline_apply_kernel<<<num_rows, block_size>>>(
            d_x, d_gate, d_up, d_residual, d_out,
            d_rms_vals, d_offsets, num_rows, threshold, sharpness
        );
    }
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaEventRecord(stop_event));
    CUDA_CHECK(cudaEventSynchronize(stop_event));
    float baseline_time_ms = 0.0f;
    CUDA_CHECK(cudaEventElapsedTime(&baseline_time_ms, start_event, stop_event));
    float baseline_avg_ms = baseline_time_ms / iterations;

    // Algorithmic bytes read + written. This counts each logical tensor pass,
    // including row offsets and the baseline's RMS intermediate.
    size_t bytes_fused =
        (size_t)total_elements * 5 * sizeof(float) +
        (size_t)(num_rows + 1) * sizeof(int);
    size_t bytes_baseline =
        (size_t)total_elements * 6 * sizeof(float) +
        (size_t)(2 * (num_rows + 1) + 2 * num_rows) * sizeof(int);

    double fused_bw = (double)bytes_fused / (fused_avg_ms * 1e-3) / 1e9; // GB/s
    double baseline_bw = (double)bytes_baseline / (baseline_avg_ms * 1e-3) / 1e9;
    float speedup = baseline_avg_ms / fused_avg_ms;

    printf("\nResults:\n");
    printf("  Fused kernel:   %.3f ms avg, effective bandwidth: %.2f GB/s\n", fused_avg_ms, fused_bw);
    printf("  Baseline kernel: %.3f ms avg, effective bandwidth: %.2f GB/s\n", baseline_avg_ms, baseline_bw);
    printf("  Speedup (baseline/fused): %.2fx\n", speedup);
    printf("  (Note: Speedup > 1.0 means fused is faster, < 1.0 means slower.)\n");
    printf("  (Measurements are specific to this hardware, shape, and configuration.)\n");

    // Cleanup
    CUDA_CHECK(cudaEventDestroy(start_event));
    CUDA_CHECK(cudaEventDestroy(stop_event));
    cudaFree(d_x);
    cudaFree(d_gate);
    cudaFree(d_up);
    cudaFree(d_residual);
    cudaFree(d_out);
    cudaFree(d_offsets);
    cudaFree(d_rms_vals);

    printf("\nAll tests passed.\n");
    return 0;
}
