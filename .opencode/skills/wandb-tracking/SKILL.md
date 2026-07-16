---
name: wandb-tracking
description: Inspect or configure Forge0's bounded W&B experiment records. Use when comparing queued Optuna/OpenEvolve candidates, frontier size, latency, error, resources, or when syncing durable offline runs to an approved W&B server.
---

# Forge0 W&B tracking

Experiment workers log through W&B 0.28.1 after static evaluation completes.
Offline mode is the default, so queue completion never depends on a tracking
server. Each run ID equals the durable experiment job ID.

Track raw metrics, feasibility, manifest budgets, elapsed time, and frontier
size. Never log API keys, prompts containing private data, full environment
variables, repository credentials, or unbounded command output.

Use `/lab` and `GET /api/experiments/{id}` as the operational source of truth.
W&B is an analysis mirror; a tracking outage must not change the queue result.

Before enabling online mode:

1. Verify the approved server health and TLS/auth configuration.
2. Set `WANDB_MODE=online`, `WANDB_BASE_URL`, and the worker credential through
   deployment secrets, not a manifest or repository file.
3. Submit one two-candidate smoke job and confirm its W&B run ID matches the job.
4. Return to offline mode if logging adds failure coupling or unacceptable
   latency.

Compare candidates as a Pareto set. W&B charts may visualize a projection, but
must not replace correctness constraints or collapse latency, quality, tokens,
cost, and resource use into one hidden score.
