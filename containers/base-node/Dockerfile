# Forge0 Base Node Container
# Includes: Common Node.js tools and formatters
FROM node:22-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install global Node.js tools
RUN npm install -g \
    typescript \
    ts-node \
    vitest \
    jest \
    eslint \
    prettier \
    @types/node \
    @types/jest \
    nodemon

# Install Python for TrailMark (used for code analysis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install TrailMark for Python
RUN pip3 install --no-cache-dir trailmark

WORKDIR /app

# Default command
CMD ["node", "--version"]
