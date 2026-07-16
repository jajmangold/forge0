---
name: openevolve
description: Evolutionary code optimization using MAP-Elites + LLMs — discover breakthrough algorithms, optimize performance, and find novel solutions through quality-diversity evolution
license: Apache-2.0
compatibility: opencode
metadata:
  audience: developers
  workflow: optimization
  source: https://github.com/algorithmicsuperintelligence/openevolve
---

## What I do

OpenEvolve is an evolutionary coding agent that uses MAP-Elites quality-diversity algorithms + LLM ensembles to discover breakthrough optimizations. It maintains diverse populations of code solutions and evolves them over generations.

Use it to:
- **Optimize code performance** — discover hardware-specific optimizations humans miss
- **Find novel algorithms** — explore solution spaces beyond human creativity
- **Multi-objective optimization** — balance competing goals automatically
- **GPU kernel optimization** — find hardware-aware optimizations
- **Algorithm discovery** — evolve sorting, search, and mathematical algorithms

## When to use me

- Performance optimization is critical
- You need to explore large solution spaces
- Multi-objective tradeoffs (speed vs memory vs accuracy)
- Competitive programming optimization
- Scientific computing optimization
- Hardware-specific kernel optimization

## Installation

```bash
pip install openevolve
```

## Quick Start

```bash
# Run evolution on a function
python openevolve-run.py initial_program.py evaluator.py --iterations 100

# Or use as library
from openevolve import run_evolution, evolve_function

result = run_evolution(
    initial_program="def solve(x): ...",
    evaluator=lambda path: {"score": benchmark(path)},
    iterations=100
)

# Evolve a Python function directly
result = evolve_function(
    my_function,
    test_cases=[(input, expected_output)],
    iterations=50
)
```

## Configuration

```yaml
# config.yaml
max_iterations: 1000
random_seed: 42  # Full reproducibility

llm:
  # Ensemble configuration
  models:
    - name: "gemini-2.5-pro"
      weight: 0.6
    - name: "gemini-2.5-flash"
      weight: 0.4
  temperature: 0.7

database:
  # MAP-Elites quality-diversity
  population_size: 500
  num_islands: 5  # Parallel evolution
  migration_interval: 20
  feature_dimensions: ["complexity", "diversity", "performance"]

evaluator:
  enable_artifacts: true      # Error feedback to LLM
  cascade_evaluation: true    # Multi-stage testing
  use_llm_feedback: true      # AI code quality assessment

prompt:
  # Sophisticated inspiration system
  num_top_programs: 3         # Best performers
  num_diverse_programs: 2     # Creative exploration
  include_artifacts: true     # Execution feedback
```

## How It Works

### MAP-Elites + LLMs

1. **Quality-Diversity Evolution**: Maintains diverse populations across feature dimensions
2. **Island-Based Architecture**: Multiple populations prevent premature convergence
3. **LLM Ensemble**: Multiple models with intelligent fallback strategies
4. **Artifact Side-Channel**: Error feedback improves subsequent generations

### Evolution Process

```
Initial Program → [LLM Ensemble] → Mutations
                    ↓
              [Evaluator] → Scores + Artifacts
                    ↓
              [MAP-Elites] → Diverse Population
                    ↓
              [Island Migration] → Gene Flow
                    ↓
              Next Generation → Repeat
```

## Forge0 Integration

### Code Optimization Workflow

```python
# 1. Define the initial program
initial_code = """
def optimize_this(data):
    # Current implementation
    result = []
    for item in data:
        result.append(process(item))
    return result
"""

# 2. Define the evaluator
def evaluator(program_path):
    # Run the program and measure performance
    import time
    exec(open(program_path).read())
    
    test_data = generate_test_data()
    start = time.time()
    result = optimize_this(test_data)
    elapsed = time.time() - start
    
    return {
        "score": 1.0 / elapsed,  # Higher is faster
        "correctness": check_correctness(result)
    }

# 3. Run evolution
from openevolve import run_evolution

result = run_evolution(
    initial_program=initial_code,
    evaluator=evaluator,
    iterations=200,
    config={
        "llm": {
            "api_base": "https://opencode.ai/zen/go/v1",
            "model": "mimo-v2.5"
        }
    }
)

print(f"Best solution: {result.best_code}")
print(f"Performance: {result.best_score}")
```

### Multi-Objective Optimization

```yaml
database:
  feature_dimensions:
    - "execution_time"
    - "memory_usage"
    - "code_complexity"

evaluator:
  objectives:
    - name: "speed"
      weight: 0.5
      minimize: true
    - name: "memory"
      weight: 0.3
      minimize: true
    - name: "readability"
      weight: 0.2
      maximize: true
```

### GPU Kernel Optimization

```python
# For CUDA/Metal kernel optimization
initial_kernel = """
kernel void attention(query, key, value, output) {
    // Baseline implementation
}
"""

def gpu_evaluator(program_path):
    # Compile and benchmark the kernel
    latency = benchmark_kernel(program_path)
    throughput = measure_throughput(program_path)
    
    return {
        "score": throughput / latency,
        "artifacts": {
            "profiling_data": profile_kernel(program_path),
            "memory_access_patterns": analyze_memory(program_path)
        }
    }
```

## Advanced Features

### Artifact Feedback

```python
# Evaluator can return rich feedback
from openevolve.evaluation_result import EvaluationResult

return EvaluationResult(
    metrics={"performance": 0.85, "correctness": 1.0},
    artifacts={
        "stderr": "Warning: suboptimal memory access pattern",
        "profiling_data": {...},
        "llm_feedback": "Code is correct but could use better variable names",
        "build_warnings": ["unused variable x"]
    }
)
```

### Custom Prompt Templates

```yaml
prompt:
  template_dir: "custom_templates/"
  use_template_stochasticity: true
  template_variations:
    greeting:
      - "Let's enhance this code:"
      - "Time to optimize:"
      - "Improving the algorithm:"
    improvement_suggestion:
      - "Here's how we could improve this code:"
      - "I suggest the following improvements:"
```

### System Message Best Practices

```yaml
prompt:
  system_message: |
    You are an expert programmer specializing in optimization.
    
    CONSTRAINTS:
    MUST NOT CHANGE:
    - Function signatures
    - Algorithm correctness
    - External API
    
    ALLOWED TO OPTIMIZE:
    - Internal implementation
    - Data structures
    - Performance optimizations
    
    OPTIMIZATION FOCUS:
    - Reduce time complexity
    - Minimize memory allocations
    - Exploit hardware features
    - Remove unnecessary computations
```

## Proven Results

| Domain | Achievement | Example |
|--------|-------------|---------|
| GPU Optimization | 2.8x speedup on Apple M1 Pro | MLX Metal Kernels |
| Mathematical | State-of-the-art circle packing (n=26) | Circle Packing |
| Algorithm Design | Adaptive sorting algorithms | Rust Adaptive Sort |
| Scientific Computing | Automated filter design | Signal Processing |

## Rules

- **Define clear objectives** — what "better" means must be measurable
- **Set constraints** — what can and cannot change
- **Use artifacts** — error feedback accelerates evolution
- **Start small** — fewer iterations first, then scale up
- **Monitor convergence** — know when to stop
- **Reproducibility** — use seeds for debugging

## Cost Estimation

| Model | Cost per Iteration |
|-------|-------------------|
| o3 | ~$0.15-0.60 |
| o3-mini | ~$0.03-0.12 |
| Gemini-2.5-Pro | ~$0.08-0.30 |
| Gemini-2.5-Flash | ~$0.01-0.05 |
| Local models | Nearly free |

## References

- Source: https://github.com/algorithmicsuperintelligence/openevolve
- License: Apache-2.0
- MAP-Elites: Quality-diversity evolutionary algorithm
- AlphaEvolve: DeepMind's evolutionary coding agent
