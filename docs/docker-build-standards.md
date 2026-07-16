# Docker Build Standards

Hard rules for container builds. No runaway builds, no uncached layers, no surprises.

## The Three Base Images

**Every container in the fleet builds on one of these three.** No exceptions.

### 1. `python:3.12-slim` — Services & APIs

**Use for:** FastAPI apps, Flask services, CLI tools, lightweight workers
**Size:** ~150MB base
**Already cached:** Yes (used by portal, and many existing services)

```dockerfile
FROM python:3.12-slim
```

**What it has:** Python 3.12, pip, basic Unix tools
**What it doesn't have:** Node.js, Java, GPU support, build tools

**When to use:**
- API servers (FastAPI, Flask)
- Background workers
- CLI tools
- Anything that only needs Python

---

### 2. `nvcr.io/nvidia/pytorch:23.12-py3` — GPU Workloads

**Use for:** ML inference, training, CUDA workloads, anything touching a GPU
**Size:** ~18GB base (pre-cached on NGC)
**CUDA:** 12.3.2 | **cuDNN:** 8.9.7 | **PyTorch:** 2.2.0a0
**Includes:** Nsight Compute (ncu), Nsight Systems, TensorRT, NCCL, DALI
**Architecture:** sm_70 Volta + sm_75 Turing + sm_80 Ampere

```dockerfile
FROM nvcr.io/nvidia/pytorch:23.12-py3
```

**What it has:** PyTorch, CUDA toolkit, cuDNN, NCCL, TensorRT, Nsight profiling, Python 3.10, Ubuntu 22.04
**What it doesn't have:** Node.js, Java

**When to use:**
- Any service that uses GPU (inference, training)
- CUDA kernel development
- Profiling with Nsight Compute/Systems
- PyTorch model serving

**Why 23.12 specifically:**
- Last release that fully tests on Volta (sm_70) Tensor Cores
- Includes Nsight Compute 2023.3.1.1 and Nsight Systems 2023.3.4.1
- CUDA 12.3.2 — compatible with the host's CMP 100-210 and V100 cards
- 23.06+ dropped Pascal testing; 23.12 is the sweet spot for Volta

---

### 3. `ghcr.io/catthehacker/ubuntu:act-22.04` — Full Dev/CI Runner

**Use for:** CI pipelines, development environments, anything that needs "everything"
**Size:** ~12GB base
**Includes:** Node.js, Python, Go, Java, Ruby, Rust, Docker, git, build-essential, curl, wget, jq, yq, and more

```dockerfile
FROM ghcr.io/catthehacker/ubuntu:act-22.04
```

**What it has:** Everything a GitHub Actions runner has. All languages, all tools.
**What it doesn't have:** GPU support

**When to use:**
- CI/CD pipelines (Gitea Actions)
- Development containers
- Multi-language projects
- Anything that needs "just install everything"

**Alternative (smaller):** `ghcr.io/catthehacker/ubuntu:act-latest` (smaller, fewer tools)

---

## Decision Matrix

| Need | Base Image | Size |
|---|---|---|
| Python API/worker, no GPU | `python:3.12-slim` | ~150MB |
| GPU inference/training | `nvcr.io/nvidia/pytorch:23.12-py3` | ~18GB |
| CI pipeline, multi-language | `ghcr.io/catthehacker/ubuntu:act-22.04` | ~12GB |
| Simple static site | `python:3.12-slim` or `nginx:alpine` | ~150MB |
| Database | Official image (postgres, neo4j, etc.) | varies |

**If your use case doesn't fit any of these three, ask before creating a new base.**

## Hard Rules

### Rule 1: No `RUN apt-get update` without `--no-install-recommends`

```dockerfile
# BAD — installs recommended packages, bloating image
RUN apt-get update && apt-get install -y curl

# GOOD — minimal install
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
```

### Rule 2: Always chain `RUN` commands with `&&`

Each `RUN` creates a layer. More layers = more cache misses = slower builds.

```dockerfile
# BAD — 3 layers, each cached separately
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# GOOD — 1 layer
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
```

### Rule 3: Copy requirements.txt BEFORE source code

Docker caches layers. If requirements.txt hasn't changed, pip install is cached.

```dockerfile
# GOOD — requirements cached, only source changes invalidate
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/

# BAD — any source change reinstalls all dependencies
COPY . .
RUN pip install -r requirements.txt
```

### Rule 4: Use `--no-cache-dir` for pip

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt
```

### Rule 5: Never `COPY . .` early in the Dockerfile

Copy specific files/directories. Not everything.

```dockerfile
# BAD — copies everything, including .git, docs, tests
COPY . .

# GOOD — copy only what's needed
COPY requirements.txt .
COPY app/ app/
```

### Rule 6: Use `.dockerignore`

Create `.dockerignore` in every project:

```
.git
docs
tests
*.md
.env
.env.*
__pycache__
*.pyc
.mypy_cache
.pytest_cache
```

### Rule 7: Pin base image versions in production

```dockerfile
# Development — latest is fine
FROM python:3.12-slim

# Production — pin the digest
FROM python:3.12-slim@sha256:abc123...
```

### Rule 8: Multi-stage builds for complex images

If you need build tools (gcc, make) but not at runtime:

```dockerfile
# Stage 1: build
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime
FROM python:3.12-slim
COPY --from=builder /install /usr/local
COPY app/ app/
```

### Rule 9: No `latest` tag for third-party images in docker-compose

```yaml
# BAD — breaks on upstream changes
image: some/random-image:latest

# GOOD — pinned version
image: some/random-image:1.2.3
```

Exception: Our own base images (`python:3.12-slim`, `nvcr.io/nvidia/pytorch:23.12-py3`) are stable enough for `latest`/tag use.

### Rule 10: Build timeout — abort if > 5 minutes

If a Docker build takes more than 5 minutes, something is wrong. Either:
- Too many uncached layers
- Downloading too much
- Build context is too large

**Fix it before committing.**

## Build Context Size Limits

| Context size | Status |
|---|---|
| < 1MB | Good |
| 1-10MB | Acceptable |
| 10-50MB | Warning — check .dockerignore |
| > 50MB | Rejected — fix before building |

Check build context:
```bash
# See what's in the context
docker build --no-cache -f /dev/null . 2>&1 | tail -1

# Or just check the directory size
du -sh --exclude=.git .
```

## Pre-Pull Checklist

Before building, ensure base images are cached:

```bash
# Check if image exists locally
docker images | grep "python:3.12-slim"
docker images | grep "pytorch:23.12"
docker images | grep "catthehacker/ubuntu"

# Pull if missing
docker pull python:3.12-slim
docker pull nvcr.io/nvidia/pytorch:23.12-py3
docker pull ghcr.io/catthehacker/ubuntu:act-22.04
```

## CI Build Rules (Gitea Actions)

Every CI build must:

1. **Use one of the three base images** (or an official image like `postgres:16`)
2. **Pass within 5 minutes** (build + test)
3. **Have a `.dockerignore`** to keep context small
4. **Not pull base images at build time** — pre-pull them or use a registry mirror

```yaml
# .github/workflows/ci.yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: docker build -t myapp .
      - name: Test
        run: docker run myapp pytest
```

## Image Naming Convention

```
localhost:3000/forge0/{service-name}:{version}
```

Examples:
```
localhost:3000/forge0/portal:latest
localhost:3000/forge0/portal:1.0.0
localhost:3000/forge0/research-agent:latest
```

## Registry

All images are stored in Gitea's package registry (localhost:3000).

### Push to Registry

```bash
# Login
docker login localhost:3000 -u agent -p $GITEA_TOKEN

# Tag for registry
docker tag forge0/portal:latest localhost:3000/forge0/portal:latest

# Push
docker push localhost:3000/forge0/portal:latest
```

### Use from Registry

```yaml
services:
  portal:
    image: localhost:3000/forge0/portal:latest
```

## Base Image Extension Pattern

### DO: Build on official bases

```dockerfile
# GOOD — extends official base
FROM python:3.12-slim
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ /app/
```

### DON'T: Fork base images

```dockerfile
# BAD — creates unmaintainable fork
FROM my-custom-python:1.0
```

### Extension Stack

```
Official Base (maintained by vendor)
└── Forge0 Common Layer (maintained by fleet)
    └── Per-Repo Image (maintained by project)
```

## Build Cache Optimization

### .dockerignore (critical)

```
.git
__pycache__
*.pyc
.mypy_cache
.pytest_cache
.ruff_cache
node_modules
dist
build
*.egg-info
.env
.env.*
.venv
venv
*.log
.DS_Store
```

### Layer Ordering

```dockerfile
# 1. System deps (rarely change)
RUN apt-get update && apt-get install -y --no-install-recommends curl

# 2. Language deps (change occasionally)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. App code (changes frequently)
COPY src/ /app/src/
```

### BuildKit Cache Mounts

```dockerfile
# syntax=docker/dockerfile:1

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y curl
```

## Anti-Thrashing Rules

1. **Pin versions exactly** — no :latest in Dockerfiles
2. **Use .dockerignore** — keep build context small
3. **Layer ordering** — deps before code
4. **Multi-stage builds** — separate build from runtime
5. **Deterministic builds** — same input = same output
6. **Use BuildKit cache** — never rebuild unnecessarily

## Image Size Optimization

```dockerfile
# Multi-stage for small final image
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir pyinstaller
COPY . /app
RUN cd /app && pyinstaller --onefile main.py

FROM python:3.12-slim
COPY --from=builder /app/dist/main /app/main
CMD ["/app/main"]
# Final image: ~50MB instead of ~500MB
```
