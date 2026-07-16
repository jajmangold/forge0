---
name: optillm
description: Evaluate bounded OptiLLM inference-time strategies against Forge0's direct model baseline. Use when a deterministic task set can measure whether re-reading, best-of-N, or generate-and-select improves quality enough to justify added latency and tokens.
---

# Bounded OptiLLM evaluation

OptiLLM is an optional inference strategy, not the default model gateway.

1. Establish a direct `mimo-v2.5` baseline on a fixed, versioned task set.
2. Test one approach at a time. Begin with `re2`; test `bon` or `genselect`
   only when independent evaluation can select candidates.
3. Cap candidates at 3, total model calls at 5, output at 8k tokens, and wall
   time at 180 seconds. Record random seeds where the approach supports them.
4. Archive the Pareto frontier across task quality, pass rate, latency, token
   use, cost, and answer disagreement. Do not collapse these into one score.
5. Adopt an approach only for the task class where repeated trials beat the
   direct baseline. Fall back directly when the proxy is unavailable.

Do not enable OptiLLM's web search, URL reader, memory, MCP, or code execution
plugins. Forge0 already provides bounded SearXNG research, wiki caching, static
tool contracts, and isolated execution. Keeping those boundaries separate
prevents duplicate retrieval and hidden capabilities.

Use non-pro `mimo-v2.5` for all initial samples. A Pro call is a frontier
candidate with explicit token/cost metrics, never an automatic final stage.

For OpenEvolve, benchmark direct MiMo mutations first. If an OptiLLM strategy is
proven useful, point only that experiment at the authenticated proxy and retain
the same population, token, evaluator, and wall-time limits.
