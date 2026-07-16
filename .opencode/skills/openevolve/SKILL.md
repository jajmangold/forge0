---
name: openevolve
description: Submit tiny, bounded source-evolution jobs to Forge0's OpenEvolve worker. Use when a stable evaluator can compile, test, and benchmark one narrowly delimited implementation region across multiple objectives. Do not use for broad features or repositories without a deterministic harness.
---

# Bounded OpenEvolve

OpenEvolve is an exploration lane, not an authority to merge code.

1. Choose one static harness and one exact mutation region. Preserve signatures,
   correctness contracts, external APIs, and tests.
2. Define raw metrics and constraints before evolution. Retain the quality-
   diversity archive and Pareto frontier; never accept a single opaque score.
3. Begin with population 4, one island, 2-4 iterations, one evaluator at a time,
   at most 60 changed lines, 12k LLM tokens, and 300 seconds.
4. Use non-pro `mimo-v2.5` for mutations. Escalate only a small frontier member
   when evidence shows the cheaper model is stuck.
5. Submit to `POST /api/experiments`, poll the job, and review every surviving
   diff and evaluator artifact.
6. Re-run correctness, sanitizer, and benchmark gates outside evolution before
   opening a pull request.

```json
{
  "method": "openevolve",
  "harness": "rrc-swiglu-evolve",
  "seed": 42,
  "budget": {
    "trials": 4,
    "wall_seconds": 300,
    "max_changed_lines": 60,
    "llm_tokens": 12000
  },
  "parameters": {"target": "cross_warp_reduction", "iterations": 3}
}
```

The manifest cannot supply code, commands, images, evaluators, or paths. A new
target requires a reviewed static candidate template and evaluator in
`experiments/harnesses/`.
