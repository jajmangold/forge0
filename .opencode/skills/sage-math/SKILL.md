---
name: sage-math
description: Submit bounded symbolic or exact-arithmetic checks to Forge0's networkless SageMath sandbox. Use for algebra, calculus, number theory, combinatorics, proof counterexample searches, or exact reference results that strengthen an implementation harness.
---

# SageMath sandbox

Use Sage as an evidence-producing harness, not as an unrestricted shell.

1. Reduce the question to one expression with an expected form or invariant.
2. Use only the declared symbols `x`, `y`, and `z` and Sage expression syntax.
   Imports, filesystem access, networking, subprocesses, and Python introspection
   are rejected.
3. Start with a 30-second wall limit and at most 256 KiB of output.
4. Submit the expression to `POST /api/experiments` and poll the returned id.
5. Treat a symbolic result as evidence. Preserve the expression, Sage version,
   exact output, and any independently checked examples in the consuming task.

```json
{
  "method": "sage",
  "harness": "sage-expression",
  "budget": {"trials": 1, "wall_seconds": 30, "max_output_bytes": 262144},
  "parameters": {
    "expression": "factor(x^4 - 1)",
    "expected": "(x - 1)*(x + 1)*(x^2 + 1)"
  }
}
```

The worker runs in a digest-pinned SageMath 10.8 container with no network,
read-only root filesystem, two CPUs, 2 GiB memory, and no Linux capabilities.
Add richer mathematics through a reviewed named harness instead of loosening the
expression filter.
