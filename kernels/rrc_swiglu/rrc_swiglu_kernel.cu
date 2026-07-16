// =============================================================================
// RRC-SwiGLU CUDA Kernel Implementation
// =============================================================================
//
// Ragged RMS-Confidence SwiGLU: A fused kernel that performs per-row RMS
// normalization, confidence gating, SwiGLU activation, and residual addition
// for ragged (variable-length) rows stored in a flat array with row offsets.
//
// Mathematical Operation (for row r, elements indexed i in [roff[r], roff[r+1])):
//   1. rms     = sqrt( (1/N) * sum_i(x_i^2) + eps )
//   2. n_i     = x_i / rms                        (RMS-normalized)
//   3. c_i     = sigmoid(sharpness * (|n_i| - threshold))  (confidence gate)
//   4. s_i     = silu(gate_i) * up_i               (SwiGLU activation)
//      where silu(t) = t * sigmoid(t)
//   5. y_i     = residual_i + c_i * s_i + (1 - c_i) * n_i
//
// Launch Strategy:
//   - One cooperative CUDA block per ragged row.
//   - Grid-stride element handling within each block.
//   - Two-phase reduction: warp shuffle first, then shared memory across warps.
//   - Targets compute capability 7.0+ (sm_70).
//
// Novelty Scope:
//   This is an *experimental composition* of existing operations (RMSNorm,
//   SwiGLU, confidence gating) into a single fused kernel for ragged inputs.
//   It is not a novel algorithm; the novelty is in the fusion for ragged
//   workloads. No unsupported research claims are made.
//
// Numerical Limits:
//   - Uses float computation and accumulation; very long rows or extreme inputs
//     can lose precision or overflow and should be pre-scaled by callers.
//   - Sigmoid and SILU are numerically stable (clamped to avoid overflow).
//   - eps prevents division by zero for zero-valued rows.
//   - Empty rows (N=0) are handled: output = residual (no normalization applied).
//
// Build:
//   nvcc -std=c++17 -O3 -arch=sm_70 -o rrc_swiglu_test rrc_swiglu_kernel.cu rrc_swiglu_test.cu
//   or use the provided Makefile.
//
// =============================================================================

#include <cuda_runtime.h>
#include <cstdint>
#include <cfloat>
#include "rrc_swiglu.cuh"

// ---------------------------------------------------------------------------
// Numerically stable helpers (device)
// ---------------------------------------------------------------------------

// Sigmoid: 1 / (1 + exp(-x)), stable for large |x|.
__device__ __forceinline__ float device_sigmoid(float x) {
    if (x >= 0.0f) {
        float e = __expf(-x);
        return 1.0f / (1.0f + e);
    } else {
        float e = __expf(x);
        return e / (1.0f + e);
    }
}

// SILU: x * sigmoid(x)
__device__ __forceinline__ float device_silu(float x) {
    return x * device_sigmoid(x);
}

// ---------------------------------------------------------------------------
// Warp-level sum reduction using shuffle
// ---------------------------------------------------------------------------
__device__ __forceinline__ float warp_reduce_sum(float val) {
    #pragma unroll
    for (int offset = 16; offset > 0; offset >>= 1) {
        val += __shfl_down_sync(0xFFFFFFFF, val, offset);
    }
    return val;
}

// ---------------------------------------------------------------------------
// Block-level sum reduction using shared memory + warp reduce
// ---------------------------------------------------------------------------
__device__ float block_reduce_sum(float val, float* shared, int tid, int num_threads) {
    // First reduce within warp
    int lane = tid & 31;       // tid % warpSize
    int warp_id = tid >> 5;    // tid / warpSize

    val = warp_reduce_sum(val);

    // Write reduced warp sums to shared memory
    if (lane == 0) {
        shared[warp_id] = val;
    }
    __syncthreads();

    // First warp reduces across all warp sums
    int num_warps = (num_threads + 31) >> 5;
    val = (tid < num_warps) ? shared[tid] : 0.0f;
    if (warp_id == 0) {
        val = warp_reduce_sum(val);
    }
    // Broadcast result to all threads
    if (tid == 0) {
        shared[0] = val;
    }
    __syncthreads();
    return shared[0];
}

// ---------------------------------------------------------------------------
// RRC-SwiGLU kernel
//
// Assumptions:
//   - x, gate, up, residual, out are all float* of length >= max(roff)
//   - roff is int32_t* of length (num_rows + 1), with roff[0] = 0
//     and roff[r+1] >= roff[r].
//   - One block per row.
// ---------------------------------------------------------------------------
__global__ void rrc_swiglu_kernel(
    const float* __restrict__ x,        // input for RMS normalization
    const float* __restrict__ gate,     // gate input for SwiGLU
    const float* __restrict__ up,       // up input for SwiGLU
    const float* __restrict__ residual, // residual to add
    float*       __restrict__ out,      // output
    const int32_t* __restrict__ roff,   // row offsets, length num_rows + 1
    int num_rows,
    float eps,
    float threshold,
    float sharpness
) {
    int row = blockIdx.x;
    if (row >= num_rows) return;

    int row_start = roff[row];
    int row_end   = roff[row + 1];
    int row_len   = row_end - row_start;

    int tid        = threadIdx.x;
    int block_size = blockDim.x;

    // Dynamic shared memory: used for reduction (up to blockDim.x/32 floats)
    extern __shared__ float smem[];

    // Every thread in the row's block takes the same path.
    if (row_len <= 0) return;

    // -----------------------------------------------------------------------
    // Phase 1: Compute sum of squares for RMS normalization
    // -----------------------------------------------------------------------
    float local_sum_sq = 0.0f;
    for (int i = tid; i < row_len; i += block_size) {
        float val = x[row_start + i];
        local_sum_sq += val * val;
    }

    // Block reduction of sum of squares
    float total_sum_sq = block_reduce_sum(local_sum_sq, smem, tid, block_size);

    // Compute RMS (one thread broadcasts result to shared, all read)
    __shared__ float s_rms;
    if (tid == 0) {
        float mean_sq = total_sum_sq / (float)row_len;  // safe: row_len > 0
        s_rms = sqrtf(mean_sq + eps);
    }
    __syncthreads();
    float rms = s_rms;

    // -----------------------------------------------------------------------
    // Phase 2: Compute output elements (grid-stride)
    // -----------------------------------------------------------------------
    for (int i = tid; i < row_len; i += block_size) {
        int idx = row_start + i;

        // RMS normalization
        float xi = x[idx];
        float n_i = xi / rms;

        // Confidence gate
        float abs_n = fabsf(n_i);
        float c_i = device_sigmoid(sharpness * (abs_n - threshold));

        // SwiGLU activation
        float g_i = gate[idx];
        float u_i = up[idx];
        float s_i = device_silu(g_i) * u_i;

        // Residual combination
        float r_i = residual[idx];
        float result = r_i + c_i * s_i + (1.0f - c_i) * n_i;

        out[idx] = result;
    }
}

// ---------------------------------------------------------------------------
// Host launcher
// ---------------------------------------------------------------------------

/**
 * Launch the RRC-SwiGLU kernel.
 *
 * @param x         Input array for normalization (float*, length >= max(roff))
 * @param gate      Gate array for SwiGLU (float*)
 * @param up        Up-projection array for SwiGLU (float*)
 * @param residual  Residual array (float*)
 * @param out       Output array (float*)
 * @param roff      Row offsets (int32_t*, length num_rows + 1)
 * @param num_rows  Number of ragged rows
 * @param eps       Epsilon for RMS stability
 * @param threshold Threshold for confidence gate
 * @param sharpness Sharpness (slope) for confidence gate
 * @param stream    CUDA stream (default: 0)
 */
cudaError_t launch_rrc_swiglu(
    const float* x,
    const float* gate,
    const float* up,
    const float* residual,
    float* out,
    const int32_t* roff,
    int num_rows,
    float eps,
    float threshold,
    float sharpness,
    int block_size,
    cudaStream_t stream
) {
    if (num_rows == 0) return cudaSuccess;
    if (num_rows < 0 || eps <= 0.0f || block_size < 32 || block_size > 1024 ||
        block_size % 32 != 0 || !x || !gate || !up || !residual || !out || !roff) {
        return cudaErrorInvalidValue;
    }

    int grid_size  = num_rows;  // one block per row

    // Shared memory: enough for one float per warp
    int num_warps = (block_size + 31) / 32;
    size_t shared_bytes = num_warps * sizeof(float);

    rrc_swiglu_kernel<<<grid_size, block_size, shared_bytes, stream>>>(
        x, gate, up, residual, out, roff,
        num_rows, eps, threshold, sharpness
    );

    return cudaGetLastError();
}
