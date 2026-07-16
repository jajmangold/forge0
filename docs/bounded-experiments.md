# Bounded experiments and research

Forge0 separates experiment planning from execution. Skills emit declarative
manifests; workers select a named static harness. A manifest cannot choose a
command, image, evaluator, source path, or network capability.

## Runtime lanes

| Lane | Resource | Typical loop | Hard boundary |
| --- | --- | ---: | --- |
| Optuna launch search | One V100 UUID | 2–8 seconds hot | Finite declared parameters |
| OpenEvolve source search | Same V100, serialized | 1–3 minutes | One marked region, 60 lines |
| SageMath exact check | 2 CPU, 2 GiB | About 7 seconds | Expression evaluator, no network |
| Deep research | SearXNG + MiMo | About 36 seconds cold | 2–6 queries, 4–30 sources |

The queue is SQLite in the persistent Forge0 data volume. Claims use an
exclusive transaction and a renewable lease; an expired worker lease returns a
job to the queue. GPU and Sage workers claim different resource classes.

## Multi-frontier policy

Every harness declares objective names and directions. Correctness and safety
are feasibility constraints. Forge0 retains all feasible non-dominated
candidates and does not hide tradeoffs in a weighted score.

The CUDA launch harness currently minimizes median latency, maximum absolute
error, and thread count while also reporting effective bandwidth. OpenEvolve
uses MAP-Elites internally for quality/diversity and Forge0 independently
recomputes its feasible Pareto frontier from raw evaluator metrics.

## Reproducibility and iteration speed

- The CUDA base is locked to
  `nvidia/cuda@sha256:020bc241a628776338f4d4053fed4c38f6f7f3d7eb5919fecb8de313bb8ba47c`.
- The SageMath amd64 image is locked to
  `sha256:fb96c7fb10d672f3be0d088399db3aeac52650416d1bb71f74f26429ea35778f`.
- The GPU worker pins Optuna 4.9.0, OpenEvolve 0.3.1, and W&B 0.28.1.
- `scripts/release-experiment-image.sh` is the explicit build step. Compose
  starts the resulting image with `--no-build` during operation.
- CUDA compilation is cached by source hash. Parameter-only trials reuse the
  binary and never invoke `nvcc` again.
- Seeds, manifests, raw candidates, frontiers, evaluator artifacts, and W&B run
  IDs are durable.

Measured on the bound Tesla V100-PCIE-12GB, a six-geometry Optuna run took 15.4
seconds cold and 8.1 seconds cache-hot. A two-iteration OpenEvolve run took
139.6 seconds; its LLM calls dominated evaluation time. These are local
reference measurements, not universal performance claims.

## Research reuse

Deep research fans out deterministic query angles through SearXNG, deduplicates
URLs, rejects private-address fetches, retrieves bounded public text excerpts,
and synthesizes with `mimo-v2.5`. Results expire after seven days and are
published to `Research-*` pages in the project Gitea wiki. An identical cached
lookup avoids search, model, and wiki calls.

## Operations

Build the worker only after changing its locked dependencies or source:

```sh
./scripts/release-experiment-image.sh
```

Start the immutable workers:

```sh
docker compose --profile optimization up -d --no-build experiment-worker sage-worker
```

Use `/lab` in the portal to submit jobs and inspect queue status. Machine
clients may use `POST /api/experiments` and `GET /api/experiments/{id}` through
the same authenticated portal boundary.
