# Forge0 Base Rust Container
# Includes: Rust toolchain and common tools
FROM rust:1.78-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install common Rust tools
RUN cargo install \
    cargo-audit \
    cargo-deny \
    cargo-edit \
    cargo-watch \
    cargo-expand

# Install Python for TrailMark
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install TrailMark
RUN pip3 install --no-cache-dir trailmark

WORKDIR /app

# Default command
CMD ["rustc", "--version"]
