# Agent Tooling & Resource Management

W&B, TrailMark, Optuna, GPU profiling quirk, and strict resource budgeting.

## Weights & Biases (wandb)

### When to use

W&B is integrated **when the agent sees fit**, not forced. Use wandb when:

| Use case | What to track |
|---|---|
| Model training/fine-tuning | Loss curves, accuracy, learning rate, gradients |
| Model evaluation | Metrics over time, regression detection, A/B comparisons |
| Hyperparameter sweeps | Parameter importance, sweep convergence |
| TDD regression tracking | Test pass rates, coverage trends, execution time over commits |
| Performance benchmarks | Latency, throughput, memory usage over versions |

### When NOT to use

- Simple scripts with no metrics to track
- One-off tasks with no iteration
- Projects where the overhead isn't justified

### Integration pattern

```python
import wandb

# Agent initializes a run
wandb.init(
    project="forge0-{project-name}",
    config={
        "task_id": "TASK-001",
        "requirement": "REQ-001",
        "model": "my-model-v2",
        "hyperparameters": {...},
    },
)

# Agent logs metrics
wandb.log({"loss": 0.15, "accuracy": 0.92, "step": epoch})

# Agent finishes
wandb.finish()
```

### TDD regression tracking

The Pipeline Watcher agent can log test metrics to W&B on every CI run:

```python
# After CI completes
wandb.init(project="forge0-{project}-tests")
wandb.log({
    "tests_passed": 47,
    "tests_failed": 0,
    "tests_skipped": 2,
    "coverage_pct": 87.3,
    "test_duration_sec": 12.4,
    "commit": "abc1234",
    "timestamp": datetime.now().isoformat(),
})
wandb.finish()
```

This creates a time-series of test health. The agent can detect:
- Coverage regression (dropped below threshold)
- Test duration regression (tests getting slower)
- Flaky tests (pass/fail oscillation)

### Configuration

```bash
# Environment variables (set in docker-compose or .env)
WANDB_API_KEY=your-key-here
WANDB_PROJECT=forge0
WANDB_ENTITY=your-team
WANDB_MODE=online  # online | offline | disabled
```

### Agent decision logic

```
IF project has ML components (model training, evaluation):
    USE wandb for experiment tracking
    
IF project has > 10 test files:
    USE wandb for TDD regression tracking
    
IF running hyperparameter optimization:
    USE wandb sweeps (with Optuna backend)
    
ELSE:
    DON'T integrate wandb (overhead not justified)
```

---

## TrailMark (Code Analysis)

### What it is

TrailMark (by Trail of Bits) parses source code into queryable graphs of functions, classes, calls, and semantic annotations for security analysis. It uses tree-sitter for language-agnostic AST parsing and rustworkx for high-performance graph traversal.

### When to use

| Use case | What TrailMark does |
|---|---|
| Security audit | Taint propagation analysis, blast radius mapping |
| Code review | Call graph analysis, dependency tracing |
| Refactoring | Impact analysis — what breaks if I change this function? |
| Architecture analysis | Module dependency graphs, circular dependency detection |
| Vulnerability triage | Map CVE impact across codebase |

### Integration pattern

TrailMark is a CLI tool. Agents invoke it as a subprocess:

```bash
# Build the code graph
trailmark build ./src --output graph.json

# Query the graph
trailmark query graph.json --function "authenticate"
trailmark query graph.json --taint-from "user_input" --taint-to "db_query"
```

### Agent workflow

```
Implementation Agent (after writing code):
    1. Run trailmark build on the codebase
    2. Query for blast radius of changed functions
    3. If blast radius > threshold: flag for review
    4. Store graph in .forge0/analysis/ for future reference

Critic Agent (during PR review):
    1. Load existing graph
    2. Run taint analysis on new code
    3. Check for security-sensitive paths
    4. Report findings in PR comment
```

### When to use vs not

**Use TrailMark when:**
- Security-sensitive code (auth, payments, data handling)
- Large refactoring (need impact analysis)
- PR review of critical paths
- Periodic security audits

**Don't use TrailMark when:**
- Simple CRUD changes
- Documentation-only changes
- Small, isolated feature additions

---

## Optuna (Hyperparameter Optimization)

### What it is

Optuna is an automatic hyperparameter optimization framework. It uses Bayesian optimization (Tree-structured Parzen Estimator) to efficiently search hyperparameter spaces.

### When to use

| Use case | How Optuna helps |
|---|---|
| Model fine-tuning | Find optimal learning rate, batch size, architecture params |
| Feature engineering | Find optimal feature combinations |
| Threshold tuning | Find optimal classification thresholds |
| Configuration tuning | Find optimal system parameters (pool sizes, timeouts) |

### Integration pattern

```python
import optuna

def objective(trial):
    lr = trial.suggest_float("lr", 1e-5, 1e-1, log=True)
    batch_size = trial.suggest_categorical("batch_size", [16, 32, 64, 128])
    n_layers = trial.suggest_int("n_layers", 1, 5)
    
    model = build_model(n_layers=n_layers)
    accuracy = train_and_evaluate(model, lr=lr, batch_size=batch_size)
    
    return accuracy

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)

print(f"Best trial: {study.best_trial.params}")
```

### W&B + Optuna integration

Optuna sweeps can be tracked in W&B:

```python
import wandb
import optuna

def objective(trial):
    # ... define hyperparameters ...
    wandb.init(project="forge0-sweeps", config=trial.params)
    accuracy = train_and_evaluate(...)
    wandb.log({"accuracy": accuracy})
    wandb.finish()
    return accuracy

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=50)
```

### Agent workflow

```
User: "Train a classifier on this dataset"

Implementation Agent:
    1. Build baseline model
    2. Evaluate baseline metrics
    3. IF metrics are below threshold:
        a. Create Optuna study
        b. Run optimization (50-100 trials)
        c. Log all trials to W&B
        d. Report best parameters
    4. Train final model with best parameters
    5. Log final metrics to W&B
```

### When to use vs not

**Use Optuna when:**
- Model performance needs improvement
- Hyperparameter space is large (> 3 params)
- Training is fast enough for many trials (< 10 min each)
- You want systematic exploration, not manual guessing

**Don't use Optuna when:**
- Model already performs well
- Only 1-2 hyperparameters (grid search is fine)
- Each trial takes hours (too expensive)
- No clear objective metric

---

## GPU Profiling Quirk: V100 Only

### The problem

This host has two types of GPUs that look identical (both sm_70, 16GB VRAM) but have different profiling capabilities:

| GPU Type | Indices | NCU/Nsight | Why |
|---|---|---|---|
| **Tesla V100-PCIE** | 4, 7, 9, 11, 14 | Works | Full compute GPU with profiling support |
| **CMP 100-210** | 0,1,2,3,5,6,8,10,12,13,15 | Broken/missing | Mining GPU — hardware profiling counters removed |
| **Quadro K620** | 16 | N/A | Display only, not used for compute |

### Impact

- `ncu` (Nsight Compute) — kernel-level profiling, only works on V100 indices
- `nsys` (Nsight Systems) — system-level profiling, only works on V100 indices
- CUDA compute-sanitizer — only works on V100 indices
- Basic `nvidia-smi` stats — work on all GPUs
- `torch.cuda` profiling — works on all GPUs (software-level)

### What this means for agents

When an agent needs to profile GPU code:
1. It MUST use a V100 GPU (indices 4, 7, 9, 11, 14)
2. It should detect the GPU type and warn if on a CMP card
3. Profiling results are only valid on V100 cards

### Agent awareness

```python
# Agent checks before profiling
import subprocess

def get_gpu_type(device_id: int) -> str:
    result = subprocess.run(
        ["nvidia-smi", "-i", str(device_id), "--query-gpu=name", "--format=csv,noheader"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def can_profile(device_id: int) -> bool:
    gpu_type = get_gpu_type(device_id)
    return "V100" in gpu_type or "Tesla" in gpu_type

# Agent decision
if can_profile(gpu_id):
    # Run NCU profiling
    subprocess.run(["ncu", "--target-processes", "all", "./my_app"])
else:
    # Use software-level profiling only
    # Skip hardware counters
    print(f"WARNING: GPU {gpu_id} is {get_gpu_type(gpu_id)} — no hardware counters available")
```

### Profiling workflow

```
User: "Profile this model's inference speed"

Implementation Agent:
    1. Check available GPUs
    2. Find a V100 GPU that's not in use
    3. Pin the workload to that GPU
    4. Run ncu/ncu-ui for kernel profiling
    5. Run nsys for system-level profiling
    6. Generate report
    7. Store in .forge0/profiles/

If no V100 available:
    1. Use torch.cuda.Event for software timing
    2. Use torch.profiler for PyTorch-level profiling
    3. Note in report: "Hardware counters not available (CMP GPU)"
```

---

## Resource Budgeting

### The problem

The host has finite resources:
- **121 GiB RAM** (hard limit — OOM kills the host)
- **16 GB VRAM per GPU** (17 GPUs, but only 5 support profiling)
- **72 GiB swap** (NVMe-backed, slow fallback)
- **~344 GB disk** free

Agents must be aware of and respect these limits.

### Resource budget per agent

| Resource | Budget | Enforcement |
|---|---|---|
| RAM per container | `mem_limit` in docker-compose | cgroup enforcement |
| GPU memory | 16 GB per GPU | CUDA OOM error if exceeded |
| Disk usage | Monitor via `df` | Alert at 90% |
| CPU | No hard limit | Monitor via `docker stats` |
| LLM API cost | $5/day per project | Agent self-monitoring |
| Build time | 5 min max per build | CI timeout |

### Agent resource awareness

Every agent should check resources before heavy operations:

```python
import shutil
import psutil

def check_resources():
    # Disk
    disk = shutil.disk_usage("/")
    if disk.free < 10 * 1024**3:  # 10 GB
        raise ResourceError("Less than 10 GB disk free")
    
    # RAM
    mem = psutil.virtual_memory()
    if mem.percent > 85:
        raise ResourceError(f"RAM usage at {mem.percent}%")
    
    # GPU memory (if using GPU)
    # Check via nvidia-smi or torch.cuda.mem_get_info()
```

### Resource monitoring (continuous)

The Pipeline Watcher agent monitors:

```
Every 5 minutes:
    1. Check docker stats (RAM, CPU per container)
    2. Check nvidia-smi (GPU memory, utilization)
    3. Check df (disk usage)
    4. If any metric exceeds threshold:
        a. Alert user via portal
        b. Log to .forge0/resource-alerts.md
        c. If critical: restart offending container
```

### Cost budgeting (LLM API)

Each project gets a daily LLM budget:

```yaml
# .forge0/project.yaml
budget:
  llm_daily_usd: 5.00
  llm_monthly_usd: 50.00
  alert_at_pct: 80    # alert when 80% used
  hard_limit: true     # stop agents when budget exceeded
```

The orchestrator tracks cumulative cost per project and refuses to invoke agents when budget is exceeded.

### Container memory limits (current fleet)

From AGENTS.md — sum of all caps (~168 GiB) must stay below RAM + swap (~192 GiB):

| Service | mem_limit | Notes |
|---|---|---|
| Gitea | 4g | Lightweight |
| Portal | 512m | Lightweight |
| SearXNG | 512m | Lightweight |
| GPU services | 8-16g each | Heavy — watch carefully |

**Rule:** Never increase a mem_limit without checking the total against available RAM + swap.

---

## Portal UX

The user portal shows:
- **W&B dashboards** — embedded or linked (when wandb is configured)
- **TrailMark reports** — security analysis results (when run)
- **Optuna results** — hyperparameter optimization history (when run)
- **Resource usage** — current RAM, GPU, disk, cost status
- **GPU status** — which GPUs are in use, which support profiling

The user does NOT see:
- Internal agent orchestration details
- Raw CI logs (unless they click through)
- Container internals
- API keys or tokens
