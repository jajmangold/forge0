#pragma once

#include <cuda_runtime.h>
#include <cstdint>
#include <cstddef>

/**
 * @file rrc_swiglu.cuh
 * @brief Header for experimental Ragged RMS-Confidence SwiGLU CUDA kernel
 * 
 * Mathematical operation for element i in a row:
 *   n = x_i / sqrt(mean(x^2) + eps)
 *   confidence = sigmoid(sharpness * (|n| - threshold))
 *   swiglu = silu(gate_i) * up_i
 *   output = residual_i + confidence * swiglu + (1 - confidence) * n
 * 
 * Launch strategy: One cooperative block per ragged row, grid-stride element
 * handling, warp-shuffle plus shared-memory reduction for RMS computation.
 * 
 * Novelty scope: Experimental composition of existing techniques (RMS norm,
 * confidence gating, SwiGLU, residual addition) for ragged row processing.
 * Not an unsupported research claim.
 * 
 * Numerical limits: Uses float32 with epsilon for stability. Input should
 * avoid extreme values to prevent overflow in squaring operations.
 */

/**
 * @brief Launch the fused RRC-SwiGLU kernel for ragged rows.
 * 
 * @param x           Input array [total_elements] (read-only)
 * @param gate        Gate array for SwiGLU [total_elements] (read-only)
 * @param up          Up array for SwiGLU [total_elements] (read-only)
 * @param residual    Residual array [total_elements] (read-only)
 * @param output      Output array [total_elements] (write-only)
 * @param row_offsets  Array of row offsets [num_rows + 1] (read-only)
 *                  row_offsets[i] is start index of row i, row_offsets[num_rows] is total_elements
 * @param num_rows    Number of ragged rows
 * @param eps         Positive RMS-normalization epsilon
 * @param threshold   Confidence threshold
 * @param sharpness   Confidence sigmoid slope
 * @param block_size  Cooperative block size (32..1024, multiple of 32)
 * @param stream      CUDA stream for async execution (default: 0)
 * @return cudaError_t Returns cudaSuccess on success
 * 
 * Requirements:
 * - All arrays must be allocated on GPU with sufficient size
 * - row_offsets must be non-decreasing with row_offsets[0] == 0
 * - row_offsets[num_rows] == total_elements
 * - x, gate, up, residual must have at least total_elements elements
 * - output must have at least total_elements elements
 */
cudaError_t launch_rrc_swiglu(
    const float* x,
    const float* gate,
    const float* up,
    const float* residual,
    float* output,
    const int32_t* row_offsets,
    int num_rows,
    float eps,
    float threshold,
    float sharpness,
    int block_size = 256,
    cudaStream_t stream = 0
);
