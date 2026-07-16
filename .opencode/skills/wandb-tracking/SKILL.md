---
name: wandb-tracking
description: Experiment tracking with Weights & Biases — log agent runs, metrics, artifacts, and create dashboards
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: tracking
---

## What I do

Track all agent experiments with Weights & Biases — log runs, metrics, artifacts, and create interactive dashboards.

## When to use me

- Running agent tasks
- Tracking LLM costs
- Monitoring code quality
- Comparing different approaches
- Visualizing optimization progress

## Setup

```python
import wandb

# Initialize project
wandb.init(project="forge0", entity="forge0-team")

# Or for specific task
wandb.init(
    project="forge0",
    name="task-42-auth-implementation",
    tags=["agent:coder", "model:mimo-v2.5", "project:auth"],
    config={
        "agent": "coder",
        "model": "mimo-v2.5",
        "task_id": 42,
        "max_tokens": 100000,
    }
)
```

## Metrics to Track

### Agent Performance

```python
# Track agent run
wandb.log({
    "agent/coder/success": 1,
    "agent/coder/duration_seconds": 120,
    "agent/coder/iterations": 5,
    "agent/coder/files_changed": 3,
})
```

### LLM Usage

```python
# Track LLM metrics
wandb.log({
    "llm/tokens/input": 15000,
    "llm/tokens/output": 5000,
    "llm/cost_usd": 0.15,
    "llm/latency_ms": 2500,
    "llm/model": "mimo-v2.5",
})
```

### Code Quality

```python
# Track quality metrics
wandb.log({
    "quality/test_coverage": 0.85,
    "quality/mutation_score": 0.72,
    "quality/lint_errors": 0,
    "quality/type_errors": 0,
    "quality/security_findings": 0,
})
```

### Build Metrics

```python
# Track build performance
wandb.log({
    "build/duration_seconds": 45,
    "build/cache_hits": 3,
    "build/cache_misses": 1,
    "build/image_size_mb": 150,
})
```

## Artifacts

### Store Generated Code

```python
# Create artifact for generated code
artifact = wandb.Artifact("task-42-code", type="code")
artifact.add_dir("src/")
wandb.log_artifact(artifact)
```

### Store Test Results

```python
# Create artifact for test results
artifact = wandb.Artifact("task-42-tests", type="test-results")
artifact.add_file("test-results.json")
wandb.log_artifact(artifact)
```

### Store Security Findings

```python
# Create artifact for security scan
artifact = wandb.Artifact("task-42-security", type="security")
artifact.add_file("semgrep.json")
artifact.add_file("bandit.json")
wandb.log_artifact(artifact)
```

## Dashboards

### Agent Performance Dashboard

```python
# Create dashboard panels
wandb.log({
    "dashboard/agent_success_rate": wandb.plot.bar(
        wandb.Table(columns=["Agent", "Success Rate"]),
        "Agent", "Success Rate",
        title="Agent Success Rate"
    ),
})
```

### Cost Tracking Dashboard

```python
# Create cost visualization
wandb.log({
    "dashboard/cost_by_agent": wandb.plot.bar(
        wandb.Table(columns=["Agent", "Cost"]),
        "Agent", "Cost",
        title="Cost by Agent"
    ),
})
```

## Integration with Forge0

### Agent Wrapper

```python
class WandbAgent:
    def __init__(self, agent_name: str, task_id: int):
        self.agent_name = agent_name
        self.task_id = task_id
        self.run = None
    
    def __enter__(self):
        self.run = wandb.init(
            project="forge0",
            name=f"{self.agent_name}-task-{self.task_id}",
            tags=[f"agent:{self.agent_name}", f"task:{self.task_id}"],
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            wandb.log({"error": str(exc_val)})
        wandb.finish()
    
    def log(self, metrics: dict):
        wandb.log(metrics)
```

### Usage

```python
# Track agent run
with WandbAgent("coder", 42) as agent:
    # Run agent
    result = run_agent(task)
    
    # Log metrics
    agent.log({
        "success": result.success,
        "duration": result.duration,
        "tokens_used": result.tokens,
    })
```

## Rules

- **Always initialize W&B** — every agent run must be tracked
- **Log key metrics** — success, duration, cost, quality
- **Store artifacts** — code, tests, security findings
- **Use tags** — agent type, model, project
- **Create dashboards** — visualize trends
- **Set alerts** — notify on cost/quality issues
