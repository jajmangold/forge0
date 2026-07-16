---
name: cuda-dev
description: CUDA development workflow — kernel programming, profiling, memory management, and SM architecture optimization
license: MIT
compatibility: opencode
metadata:
  audience: developers
  language: cuda
---

## What I do

CUDA development workflow for GPU programming, profiling, and optimization.

## When to use me

- Writing CUDA kernels
- Profiling GPU performance
- Optimizing memory access
- Managing GPU resources
- Debugging CUDA code

## Toolchain

```bash
# Compile
nvcc -o output source.cu

# Compile with architecture
nvcc -arch=sm_70 -o output source.cu  # Volta (V100, CMP 100-210)
nvcc -arch=sm_75 -o output source.cu  # Turing
nvcc -arch=sm_80 -o output source.cu  # Ampere

# Profile with Nsight Compute
ncu --set full ./output

# Profile with Nsight Systems
nsys profile ./output

# Memory check
compute-sanitizer ./output
```

## Kernel Pattern

```cuda
__global__ void my_kernel(const float* input, float* output, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        output[idx] = input[idx] * 2.0f;
    }
}

// Launch
int blocks = (n + 255) / 256;
my_kernel<<<blocks, 256>>>(d_input, d_output, n);
cudaDeviceSynchronize();
```

## Memory Management

```cuda
// Allocate
float* d_data;
cudaMalloc(&d_data, size);

// Copy host to device
cudaMemcpy(d_data, h_data, size, cudaMemcpyHostToDevice);

// Copy device to host
cudaMemcpy(h_data, d_data, size, cudaMemcpyDeviceToHost);

// Free
cudaFree(d_data);
```

## Error Handling

```cuda
cudaError_t err = cudaMalloc(&d_data, size);
if (err != cudaSuccess) {
    fprintf(stderr, "CUDA error: %s\n", cudaGetErrorString(err));
    return 1;
}

// Or use macro
#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            fprintf(stderr, "CUDA error at %s:%d: %s\n", \
                    __FILE__, __LINE__, cudaGetErrorString(err)); \
            exit(1); \
        } \
    } while(0)
```

## SM 70 Optimization (Volta)

```cuda
// Use shared memory for coalesced access
__shared__ float shared[256];

// Avoid bank conflicts
int idx = threadIdx.x;
int bank = idx % 32;

// Use warp-level primitives
unsigned mask = __activemask();
int leader = __ffs(mask) - 1;
```

## Profiling Workflow

```bash
# 1. Baseline
ncu --set full ./output

# 2. Identify bottlenecks
# Look at:
# - Memory throughput (should be high)
# - Compute throughput (should be high)
# - Occupancy (should be > 50%)
# - Register usage (too many = low occupancy)

# 3. Optimize
# - Reduce global memory accesses
# - Use shared memory
# - Increase occupancy
# - Use vectorized loads

# 4. Re-profile
ncu --set full ./output
```

## Testing

```cuda
// Simple test
void test_kernel() {
    int n = 1024;
    float *h_input, *h_output, *d_input, *d_output;
    
    // Allocate host
    h_input = (float*)malloc(n * sizeof(float));
    h_output = (float*)malloc(n * sizeof(float));
    
    // Initialize
    for (int i = 0; i < n; i++) h_input[i] = i;
    
    // Allocate device
    cudaMalloc(&d_input, n * sizeof(float));
    cudaMalloc(&d_output, n * sizeof(float));
    
    // Copy and run
    cudaMemcpy(d_input, h_input, n * sizeof(float), cudaMemcpyHostToDevice);
    my_kernel<<<(n+255)/256, 256>>>(d_input, d_output, n);
    cudaMemcpy(h_output, d_output, n * sizeof(float), cudaMemcpyDeviceToHost);
    
    // Verify
    for (int i = 0; i < n; i++) {
        assert(h_output[i] == h_input[i] * 2.0f);
    }
    
    // Cleanup
    free(h_input); free(h_output);
    cudaFree(d_input); cudaFree(d_output);
}
```

## Rules

- **Always check CUDA errors** — don't ignore return values
- **Profile before optimizing** — measure, don't guess
- **Use compute-sanitizer** — catch memory errors early
- **Test on target architecture** — sm_70 for our hardware
- **Document memory layout** — explain data movement
- **Benchmark against baseline** — prove improvements
