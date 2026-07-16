#!/usr/bin/env bash
set -euo pipefail

IMAGE=${FORGE0_EXPERIMENT_IMAGE:-forge0-experiment-worker:cuda129-oe031}
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

docker build --pull=false --tag "$IMAGE" --file "$ROOT/experiments/Dockerfile" "$ROOT"
docker image inspect "$IMAGE" --format 'built {{.Id}}'
