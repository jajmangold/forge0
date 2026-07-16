---
name: optuna-optimize
description: Submit small, bounded parameter-search jobs to Forge0's durable Optuna queue. Use when tuning declared knobs against measured objectives, especially latency, correctness, resource use, quality, or cost tradeoffs. Do not use for source-code mutation.
---

# Bounded Optuna optimization

Use the static harness registry. Never install packages, invent a command, select
an image, or pass a host path. Keep each job granular enough to finish in minutes.

1. State the invariant and the finite knobs that may change.
2. Declare every measurable objective and its direction. Keep correctness and
   safety as constraints; do not hide tradeoffs in a weighted scalar.
3. Start with 6-12 trials, 1-2 repetitions, a fixed seed, and at most 300 seconds.
4. Submit a validated manifest to `POST /api/experiments`.
5. Poll `GET /api/experiments/{id}` and inspect the complete Pareto frontier.
6. Promote a candidate only after an independent verification run.

For the CUDA launch harness:

```json
{
  "method": "optuna",
  "harness": "rrc-swiglu-launch",
  "seed": 42,
  "budget": {"trials": 8, "wall_seconds": 300, "repetitions": 2},
  "parameters": {
    "block_sizes": [32, 64, 128, 256, 512, 1024],
    "num_rows": 128,
    "max_row_len": 2048,
    "iterations": 100
  }
}
```

The worker compiles a source hash once, reuses it across trials, and archives
non-dominated latency/error/thread-count candidates. Add new search spaces by
implementing and testing a named static harness, never by widening the manifest.
