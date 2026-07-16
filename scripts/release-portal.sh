#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

STATE_DIR=${FORGE0_RELEASE_STATE_DIR:-$ROOT/.forge0-runtime/releases}
CANARY_NAME=${FORGE0_CANARY_NAME:-forge0-portal-canary}
CANARY_PORT=${FORGE0_CANARY_PORT:-3301}
ENV_ARGS=(--env-file .env --env-file .env.generated)
mkdir -p "$STATE_DIR"

image_from_file() {
  local file=$1
  sed -n 's/^PORTAL_IMAGE=//p' "$file" | head -1
}

wait_ready() {
  local url=$1
  local attempts=${2:-60}
  local index
  for index in $(seq 1 "$attempts"); do
    if curl -fsS "$url/healthz" >/dev/null 2>&1 \
      && curl -fsS "$url/readyz" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

write_state() {
  local destination=$1
  local image=$2
  local source_commit=$3
  local image_tag=$4
  local temporary="${destination}.tmp"
  {
    printf 'PORTAL_IMAGE=%s\n' "$image"
    printf 'SOURCE_COMMIT=%s\n' "$source_commit"
    printf 'IMAGE_TAG=%s\n' "$image_tag"
    printf 'RECORDED_AT=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >"$temporary"
  mv "$temporary" "$destination"
}

promote() {
  local image=$1
  FORGE0_PORTAL_IMAGE="$image" docker compose "${ENV_ARGS[@]}" \
    up -d --force-recreate --no-deps --no-build portal
  wait_ready http://localhost:3001
}

release() {
  local commit tag image previous_image canary_id
  commit=$(git rev-parse --verify HEAD)
  tag="forge0-portal:release-${commit:0:12}"
  previous_image=$(docker inspect --format '{{.Image}}' forge0-portal)
  docker tag "$previous_image" "forge0-portal:rollback-${previous_image#sha256:}"

  if ! docker image inspect "$tag" >/dev/null 2>&1; then
    docker build --provenance=false --tag "$tag" portal
  fi
  image=$(docker image inspect --format '{{.Id}}' "$tag")

  docker rm -f "$CANARY_NAME" >/dev/null 2>&1 || true
  trap 'docker rm -f "$CANARY_NAME" >/dev/null 2>&1 || true' EXIT
  canary_id=$(FORGE0_PORTAL_IMAGE="$image" FORGE0_SUPERVISOR_ENABLED=false \
    docker compose "${ENV_ARGS[@]}" run -d --no-deps --name "$CANARY_NAME" \
    -p "127.0.0.1:${CANARY_PORT}:3001" portal)
  if ! wait_ready "http://localhost:${CANARY_PORT}"; then
    docker logs "$canary_id" >&2 || true
    printf 'Portal canary failed; production was not changed.\n' >&2
    return 1
  fi
  docker rm -f "$CANARY_NAME" >/dev/null
  trap - EXIT

  write_state "$STATE_DIR/previous.env" "$previous_image" unknown \
    "forge0-portal:rollback-${previous_image#sha256:}"
  if ! promote "$image"; then
    printf 'Portal promotion failed; restoring %s.\n' "$previous_image" >&2
    promote "$previous_image"
    return 1
  fi
  docker tag "$image" forge0-portal:current
  write_state "$STATE_DIR/current.env" "$image" "$commit" "$tag"
  printf 'Portal release %s is healthy at immutable image %s.\n' "$commit" "$image"
}

rollback() {
  local current previous
  if [[ ! -f "$STATE_DIR/previous.env" ]]; then
    printf 'No previous portal release is recorded in %s.\n' "$STATE_DIR" >&2
    return 1
  fi
  previous=$(image_from_file "$STATE_DIR/previous.env")
  current=$(docker inspect --format '{{.Image}}' forge0-portal)
  if [[ -z "$previous" ]]; then
    printf 'Previous portal release metadata is invalid.\n' >&2
    return 1
  fi
  promote "$previous"
  docker tag "$previous" forge0-portal:current
  write_state "$STATE_DIR/current.env" "$previous" rollback rollback
  write_state "$STATE_DIR/previous.env" "$current" rollback rollback
  printf 'Portal rolled back to immutable image %s.\n' "$previous"
}

case "${1:-release}" in
  release) release ;;
  rollback) rollback ;;
  *) printf 'Usage: %s [release|rollback]\n' "$0" >&2; exit 2 ;;
esac
