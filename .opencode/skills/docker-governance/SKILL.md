---
name: docker-governance
description: Docker image governance — base image extension, package registry, build cache optimization, and anti-thrashing patterns
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: docker
---

## What I do

Manage Docker images cleanly — extend base images without sprawl, use Gitea package registry, optimize build caches, and prevent build thrashing.

## Core Principles

1. **Extend, don't fork** — Build on base images, don't copy them
2. **One registry, per repo** — Store images in Gitea package registry
3. **Cache everything** — BuildKit cache mounts
4. **Deterministic builds** — Pin versions, reproducible

## Base Image Extension Pattern

### DO: Multi-stage builds on official bases

```dockerfile
# GOOD — extends the base image
FROM python:3.12-slim AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY app/ /app/
CMD ["python", "/app/main.py"]
```

### DON'T: Fork base images

```dockerfile
# BAD — creates a new base image to maintain
FROM my-custom-python:1.0
# Now you have to maintain this forever
```

### Extension Stack

```
Official Base Images
├── python:3.12-slim
├── node:22-bookworm-slim
├── rust:1.78-slim
├── gcc:14-bookworm
└── nvidia/cuda:12.9.1-devel-ubuntu24.04

Forge0 Common Layers (built from official bases)
├── forge0/python-base:latest     # python + common deps
├── forge0/node-base:latest       # node + common deps
├── forge0/rust-base:latest       # rust + common deps
└── forge0/cuda-python:latest     # cuda + python

Per-Repo Images (built from Forge0 bases)
├── forge0/portal:latest
├── forge0/agent-core:latest
└── forge0/worker:latest
```

## Gitea Package Registry

### Store images per repo

```bash
# Tag image for repo package registry
docker tag myapp:latest localhost:3000/forge0/myapp:latest

# Login to Gitea registry
docker login localhost:3000 -u agent -p $GITEA_TOKEN

# Push to repo's package store
docker push localhost:3000/forge0/myapp:latest

# Pull from anywhere in the fleet
docker pull localhost:3000/forge0/myapp:latest
```

### Use in docker-compose

```yaml
services:
  myapp:
    image: localhost:3000/forge0/myapp:latest
    # Or use build with cache from registry
    build:
      context: .
      cache_from:
        - localhost:3000/forge0/myapp:cache
```

## Build Cache Optimization

### Dockerfile best practices

```dockerfile
# 1. Copy requirements FIRST (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy source SECOND (invalidate on change)
COPY src/ /app/src/

# 3. Use BuildKit cache mounts
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# 4. Use multi-stage to separate build from runtime
FROM builder AS runtime
COPY --from=builder /app /app
```

### BuildKit optimizations

```dockerfile
# syntax=docker/dockerfile:1

# Cache mount for pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Cache mount for apt
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y curl

# Cache mount for cargo
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cargo build --release
```

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
.env.local
*.log
.DS_Store
docker-compose*.yaml
```

## Anti-Thrashing Patterns

### 1. Deterministic builds

```dockerfile
# Pin versions exactly
FROM python:3.12.4-slim@sha256:abc123...
RUN pip install --no-cache-dir fastapi==0.111.0 uvicorn==0.30.1

# Don't use :latest in builds
FROM python:3.12.4-slim  # GOOD
FROM python:latest        # BAD
```

### 2. Build only when needed

```yaml
# docker-compose.yaml
services:
  myapp:
    build:
      context: .
      dockerfile: Dockerfile
      # Only rebuild if these change
      args:
        BUILDKIT_INLINE_CACHE: 1
    image: localhost:3000/forge0/myapp:latest
    # Use pre-built image if available
```

### 3. Layer caching strategy

```dockerfile
# Layer 1: System deps (rarely changes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Layer 2: Language deps (changes occasionally)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer 3: App code (changes frequently)
COPY src/ /app/src/

# Layer 4: Config (changes rarely)
COPY config/ /app/config/
```

### 4. Build cache sharing

```bash
# Use BuildKit inline cache
DOCKER_BUILDKIT=1 docker build \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    -t myapp:latest .

# Push with cache
docker push myapp:latest

# Pull and use as cache
docker pull myapp:latest
docker build \
    --cache-from myapp:latest \
    -t myapp:latest .
```

## Build Workflow

### CI/CD Pipeline

```yaml
# .gitea/workflows/docker-build.yaml
name: Docker Build & Push
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Gitea Registry
        uses: docker/login-action@v3
        with:
          registry: localhost:3000
          username: agent
          password: ${{ secrets.GITEA_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            localhost:3000/${{ github.repository }}:latest
            localhost:3000/${{ github.repository }}:${{ github.sha }}
          cache-from: type=registry,ref=localhost:3000/${{ github.repository }}:cache
          cache-to: type=registry,ref=localhost:3000/${{ github.repository }}:cache,mode=max
```

### Local Development

```bash
# Build with cache
DOCKER_BUILDKIT=1 docker build \
    --cache-from localhost:3000/forge0/myapp:latest \
    -t myapp:dev .

# Use in compose
docker compose up -d

# After changes, rebuild efficiently
docker compose build  # Uses BuildKit cache
```

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

## Cleanup Policy

```bash
# Remove dangling images
docker image prune -f

# Remove unused images
docker image prune -a -f

# Remove build cache older than 7 days
docker builder prune --filter "until=168h" -f

# Remove all build cache
docker builder prune -a -f
```

## Rules

1. **No forked base images** — extend official or Forge0 common bases
2. **Pin all versions** — no :latest in Dockerfiles
3. **Use .dockerignore** — keep build context small
4. **Layer ordering** — deps before code
5. **Multi-stage builds** — separate build from runtime
6. **Store in package registry** — every image goes to Gitea
7. **Use BuildKit cache** — never rebuild unnecessarily
8. **Deterministic builds** — same input = same output
9. **Cleanup regularly** — prune unused images
10. **Document base choices** — why this base image?
