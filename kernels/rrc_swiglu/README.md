# Ragged RMS-Confidence SwiGLU CUDA kernel

RRC-SwiGLU is an experimental fusion for ragged rows stored in flat arrays. For
element `i` in a row it computes:

```text
n          = x_i / sqrt(mean(x^2) + epsilon)
confidence = sigmoid(sharpness * (abs(n) - threshold))
swiglu     = silu(gate_i) * up_i
output     = residual_i + confidence * swiglu + (1 - confidence) * n
```

The novelty is limited to this composition and fusion for ragged storage. RMS
normalization, confidence gates, SwiGLU, residual connections, and cooperative
reductions are established techniques; this is not a claim of a novel
algorithm or universally superior performance.

## Launch strategy and limits

- One cooperative block handles each row.
- Threads traverse long rows with a grid-stride loop.
- RMS uses warp shuffles followed by a shared-memory cross-warp reduction.
- Empty rows return without reading or writing elements. Deterministic checks
  include empty, singleton, odd, warp-boundary, non-warp-multiple, and the
  requested maximum row length.
- The launcher accepts block sizes from 32 through 1024 in multiples of 32.
- Data and accumulation are `float`. Very large magnitudes may overflow while
  squaring; callers should pre-scale extreme inputs. Positive epsilon prevents
  division by zero for non-empty zero-valued rows.
- Row offsets are signed 32-bit values. The executable rejects requested shapes
  whose conservative flattened size could exceed `INT_MAX`.
- The launcher validates pointers, epsilon, row count, and launch geometry, but
  callers remain responsible for device allocation sizes and monotonic offsets.

## Build and run

Requirements are CUDA 12.x, a compute-capability 7.0 or newer GPU, and GNU Make.
There are no third-party library dependencies.

```sh
make
./rrc_swiglu_test --num_rows 128 --max_row_len 2048 --iterations 100 \
  --epsilon 1e-5 --threshold 0.5 --sharpness 10 --block_size 256
make run-bench-large
make run-pinned-cuda GPU=4
```

`run-pinned-cuda` locks the CUDA 12.9.1 devel image by digest, compiles for
`sm_70`, checks block sizes 32, 256, and 1024, then records the reference
100-iteration benchmark. `GPU` is the host device index and defaults to `0`.

Run `./rrc_swiglu_test --help` or `make help` for every supported option. The
program always runs the CPU-reference correctness checks before benchmarking
and exits nonzero for CUDA failures, non-finite output, or combined
absolute/relative tolerance failure.

## Benchmark accounting and measured evidence

Effective bandwidth is algorithmic bytes divided by CUDA-event elapsed time.
The fused count includes four input arrays, one output array, and row offsets.
The two-pass count additionally includes its separate input pass, two offset
passes, and RMS intermediate write/read. It is not a hardware-counter result.

The following is measured output, not illustrative data, from CUDA 12.9.1 on a
Tesla V100-PCIE-12GB (`sm_70`). Results depend on hardware, shape, build, and
configuration and do not imply a universal speedup:

```text
=== Correctness Test (Fused Kernel) ===
Fused kernel: PASS
  Max absolute error: 2.384186e-07

=== Benchmark (iterations=100) ===
Results:
  Fused kernel:   0.013 ms avg, effective bandwidth: 10.59 GB/s
  Baseline kernel: 0.017 ms avg, effective bandwidth: 9.74 GB/s
  Speedup (baseline/fused): 1.31x
```

That sample used 24 rows, an explicitly present 2048-element maximum row, a
256-thread block, and 6,850 total elements. NVIDIA Compute Sanitizer memcheck,
racecheck, and synccheck reported zero errors or hazards across tested block
sizes 32, 256, and 1024. Sanitizer timings are intentionally not performance
measurements.
