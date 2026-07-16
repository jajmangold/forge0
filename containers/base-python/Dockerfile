# Forge0 Base Python Container
# Includes: TrailMark, OptiLLM, OpenEvolve, and common tools
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install TrailMark
RUN pip install --no-cache-dir trailmark

# Install OptiLLM
RUN pip install --no-cache-dir optillm

# Install OpenEvolve
RUN pip install --no-cache-dir openevolve

# Install common Python tools
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    pytest-asyncio \
    ruff \
    mypy \
    pyright \
    black \
    isort \
    pylint \
    bandit \
    safety \
    pip-audit

# Install httpx for API calls
RUN pip install --no-cache-dir httpx

WORKDIR /app

# Default command
CMD ["python", "--version"]
