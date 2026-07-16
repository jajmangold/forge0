---
name: optuna-optimize
description: Hyperparameter optimization with Optuna — optimize agent prompts, model parameters, and workflow configurations
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: optimization
---

## What I do

Optimize hyperparameters with Optuna — find optimal agent prompts, model settings, and workflow configurations.

## When to use me

- Optimizing agent performance
- Tuning model parameters
- Finding optimal workflows
- Balancing cost vs quality

## Setup

```python
import optuna

# Create study
study = optuna.create_study(
    name="forge0-agent-optimization",
    direction="maximize",  # or "minimize" for cost
    storage="sqlite:///forge0_optuna.db",
    load_if_exists=True,
)

# Optimize
study.optimize(objective, n_trials=100)
```

## Use Cases

### 1. Prompt Optimization

```python
def prompt_objective(trial):
    # Suggest prompt parameters
    temperature = trial.suggest_float("temperature", 0.0, 1.0)
    max_tokens = trial.suggest_int("max_tokens", 1000, 10000)
    system_prompt = trial.suggest_categorical("system_prompt", [
        "concise", "detailed", "technical", "creative"
    ])
    
    # Run agent with parameters
    result = run_agent(
        prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    # Return score
    return result.quality_score

# Optimize
study.optimize(prompt_objective, n_trials=50)
```

### 2. Model Selection

```python
def model_objective(trial):
    # Suggest model parameters
    model = trial.suggest_categorical("model", [
        "mimo-v2.5", "mimo-v2.5-pro", "gpt-4o", "claude-sonnet"
    ])
    temperature = trial.suggest_float("temperature", 0.0, 1.0)
    
    # Run with model
    result = run_agent(model=model, temperature=temperature)
    
    # Balance quality and cost
    quality = result.quality_score
    cost = result.cost_usd
    
    return quality - 0.1 * cost  # Penalize high cost

# Optimize
study.optimize(model_objective, n_trials=30)
```

### 3. Workflow Optimization

```python
def workflow_objective(trial):
    # Suggest workflow parameters
    use_planner = trial.suggest_categorical("use_planner", [True, False])
    use_reviewer = trial.suggest_categorical("use_reviewer", [True, False])
    max_iterations = trial.suggest_int("max_iterations", 1, 10)
    
    # Run workflow
    result = run_workflow(
        use_planner=use_planner,
        use_reviewer=use_reviewer,
        max_iterations=max_iterations,
    )
    
    return result.efficiency_score

# Optimize
study.optimize(workflow_objective, n_trials=20)
```

### 4. Test Generation Optimization

```python
def test_objective(trial):
    # Suggest test parameters
    coverage_target = trial.suggest_float("coverage_target", 0.7, 0.95)
    mutation_score_target = trial.suggest_float("mutation_score_target", 0.6, 0.9)
    max_tests = trial.suggest_int("max_tests", 10, 100)
    
    # Generate tests
    result = generate_tests(
        coverage_target=coverage_target,
        mutation_score_target=mutation_score_target,
        max_tests=max_tests,
    )
    
    # Balance coverage and generation time
    coverage = result.coverage
    generation_time = result.generation_time
    
    return coverage - 0.01 * generation_time

# Optimize
study.optimize(test_objective, n_trials=40)
```

## W&B Integration

### Track Optuna Trials in W&B

```python
import wandb
import optuna

def wandb_objective(trial):
    # Initialize W&B run for this trial
    wandb.init(
        project="forge0-optimization",
        name=f"trial-{trial.number}",
        config=trial.params,
        tags=["optuna", f"trial:{trial.number}"],
    )
    
    # Run optimization
    result = run_optimization(trial)
    
    # Log metrics
    wandb.log({
        "trial/number": trial.number,
        "trial/value": result.value,
        "trial/params": trial.params,
    })
    
    # Log artifacts
    if result.artifacts:
        artifact = wandb.Artifact(f"trial-{trial.number}", type="optimization")
        for artifact_path in result.artifacts:
            artifact.add_file(artifact_path)
        wandb.log_artifact(artifact)
    
    wandb.finish()
    return result.value

# Optimize with W&B tracking
study.optimize(wandb_objective, n_trials=100)
```

### Visualize in W&B

```python
# Create optimization dashboard
wandb.log({
    "optimization/convergence": wandb.plot.line(
        wandb.Table(columns=["Trial", "Value"]),
        "Trial", "Value",
        title="Optimization Convergence"
    ),
    "optimization/params": wandb.plot.scatter(
        wandb.Table(columns=["Temperature", "Value"]),
        "Temperature", "Value",
        title="Parameter Impact"
    ),
})
```

## Analysis

### Best Parameters

```python
# Get best parameters
best_params = study.best_params
best_value = study.best_value

print(f"Best value: {best_value}")
print(f"Best parameters: {best_params}")
```

### Parameter Importance

```python
# Analyze parameter importance
import optuna.visualization as vis

fig = vis.plot_param_importances(study)
fig.show()
```

### Optimization History

```python
# Plot optimization history
fig = vis.plot_optimization_history(study)
fig.show()
```

## Rules

- **Define clear objective** — what "better" means must be measurable
- **Start with few trials** — 10-20 to understand the space
- **Use W&B tracking** — log all trials
- **Analyze results** — understand what worked
- **Apply learnings** — use best parameters in production
- **Iterate** — re-optimize as codebase changes
