#!/usr/bin/env bash
# forge0-setup.sh — Bootstrap admin user + API token after first `docker compose up -d`.
# Run after `docker compose up -d gitea`: ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERROR: .env is missing. Copy .env.example to .env and configure it first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

ADMIN_USER="${GITEA_ADMIN_USER:-agent}"
ADMIN_PASS="${GITEA_ADMIN_PASS:-agentpass123}"
ADMIN_EMAIL="${GITEA_ADMIN_EMAIL:-agent@localhost}"

echo "==> Waiting for Gitea to be healthy..."
for i in $(seq 1 60); do
  if docker compose exec -T gitea curl -fsSL http://localhost:3000/api/v1/version >/dev/null 2>&1; then
    echo "    Gitea is up."
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "ERROR: Gitea did not become healthy in 90s." >&2
    exit 1
  fi
  sleep 1.5
done

# Create admin user (skip if already exists)
echo "==> Creating admin user '${ADMIN_USER}'..."
docker exec -u git forge0 \
  gitea admin user create \
    --username "${ADMIN_USER}" \
    --password "${ADMIN_PASS}" \
    --email "${ADMIN_EMAIL}" \
    --admin \
    --must-change-password=false \
  2>/dev/null && echo "    Created." || echo "    Already exists."

# Create a fresh API token. Gitea only reveals the secret at creation time.
echo "==> Creating API token..."
EXISTING=$(docker exec -u git forge0 \
  gitea admin user generate-access-token \
    --username "${ADMIN_USER}" \
    --token-name "forge0-agent" \
    --scopes "all" \
  2>/dev/null | grep -oP '(?<=Access token was successfully created: ).*' || true)

if [ -n "$EXISTING" ]; then
  TOKEN="$EXISTING"
else
  echo "    Existing token name found; replacing it so the secret can be captured."
  EXISTING_ID=$(curl -fsS -u "${ADMIN_USER}:${ADMIN_PASS}" \
    "http://localhost:3000/api/v1/users/${ADMIN_USER}/tokens" | python3 -c '
import json
import sys

for token in json.load(sys.stdin):
    if token.get("name") == "forge0-agent":
        print(token["id"])
        break
' || true)
  if [ -n "$EXISTING_ID" ]; then
    curl -fsS -u "${ADMIN_USER}:${ADMIN_PASS}" -X DELETE \
      "http://localhost:3000/api/v1/users/${ADMIN_USER}/tokens/${EXISTING_ID}" >/dev/null
  fi
  TOKEN=$(docker exec -u git forge0 \
    gitea admin user generate-access-token \
      --username "${ADMIN_USER}" \
      --token-name "forge0-agent" \
      --scopes "all" \
    2>/dev/null | grep -oP '(?<=Access token was successfully created: ).*' || true)
fi

if [ -z "$TOKEN" ]; then
  echo "WARN: Could not get API token. Create one manually:" >&2
  echo "  docker compose exec gitea gitea admin user generate-access-token --username ${ADMIN_USER} --token-name forge0-agent --scopes all" >&2
  exit 1
fi

EXISTING_OPERATOR_TOKEN=""
EXISTING_WEBHOOK_SECRET=""
EXISTING_OAUTH_CLIENT_ID=""
EXISTING_OAUTH_CLIENT_SECRET=""
EXISTING_SESSION_SECRET=""
if [ -f .env.generated ]; then
  EXISTING_OPERATOR_TOKEN=$(sed -n 's/^FORGE0_OPERATOR_TOKEN=//p' .env.generated)
  EXISTING_WEBHOOK_SECRET=$(sed -n 's/^FORGE0_WEBHOOK_SECRET=//p' .env.generated)
  EXISTING_OAUTH_CLIENT_ID=$(sed -n 's/^GITEA_OAUTH_CLIENT_ID=//p' .env.generated)
  EXISTING_OAUTH_CLIENT_SECRET=$(sed -n 's/^GITEA_OAUTH_CLIENT_SECRET=//p' .env.generated)
  EXISTING_SESSION_SECRET=$(sed -n 's/^FORGE0_SESSION_SECRET=//p' .env.generated)
fi
OPERATOR_TOKEN="${FORGE0_OPERATOR_TOKEN:-${EXISTING_OPERATOR_TOKEN}}"
WEBHOOK_SECRET="${FORGE0_WEBHOOK_SECRET:-${EXISTING_WEBHOOK_SECRET}}"
if [ -z "$OPERATOR_TOKEN" ]; then
  OPERATOR_TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
fi
if [ -z "$WEBHOOK_SECRET" ]; then
  WEBHOOK_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
fi

OAUTH_REDIRECT_URI="${FORGE0_OAUTH_REDIRECT_URI:-http://localhost:3001/auth/callback}"
OAUTH_CLIENT_ID="${GITEA_OAUTH_CLIENT_ID:-${EXISTING_OAUTH_CLIENT_ID}}"
OAUTH_CLIENT_SECRET="${GITEA_OAUTH_CLIENT_SECRET:-${EXISTING_OAUTH_CLIENT_SECRET}}"
SESSION_SECRET="${FORGE0_SESSION_SECRET:-${EXISTING_SESSION_SECRET}}"
if [ -z "$SESSION_SECRET" ]; then
  SESSION_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
fi

echo "==> Configuring Gitea OAuth for the portal..."
OAUTH_APPS=$(curl -fsS -H "Authorization: token ${TOKEN}" \
  "http://localhost:3000/api/v1/user/applications/oauth2?limit=100")
OAUTH_APP_ID=$(printf '%s' "$OAUTH_APPS" | python3 -c '
import json
import sys

for application in json.load(sys.stdin):
    if application.get("name") == "Forge0 Portal":
        print(application["id"])
        break
' || true)
OAUTH_APP_REDIRECT=$(printf '%s' "$OAUTH_APPS" | python3 -c '
import json
import sys

for application in json.load(sys.stdin):
    if application.get("name") == "Forge0 Portal":
        print(application.get("redirect_uris", [""])[0])
        break
' || true)
if [ -z "$OAUTH_CLIENT_ID" ] || [ -z "$OAUTH_CLIENT_SECRET" ] \
  || [ -z "$OAUTH_APP_ID" ] || [ "$OAUTH_APP_REDIRECT" != "$OAUTH_REDIRECT_URI" ]; then
  export OAUTH_REDIRECT_URI
  OAUTH_PAYLOAD=$(python3 -c '
import json
import os

print(json.dumps({
    "name": "Forge0 Portal",
    "redirect_uris": [os.environ["OAUTH_REDIRECT_URI"]],
    "confidential_client": True,
    "skip_secondary_authorization": True,
}))
')
  if [ -n "$OAUTH_APP_ID" ]; then
    OAUTH_APP=$(curl -fsS -X PATCH -H "Authorization: token ${TOKEN}" \
      -H "Content-Type: application/json" -d "$OAUTH_PAYLOAD" \
      "http://localhost:3000/api/v1/user/applications/oauth2/${OAUTH_APP_ID}")
  else
    OAUTH_APP=$(curl -fsS -X POST -H "Authorization: token ${TOKEN}" \
      -H "Content-Type: application/json" -d "$OAUTH_PAYLOAD" \
      "http://localhost:3000/api/v1/user/applications/oauth2")
  fi
  OAUTH_CLIENT_ID=$(printf '%s' "$OAUTH_APP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["client_id"])')
  OAUTH_CLIENT_SECRET=$(printf '%s' "$OAUTH_APP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["client_secret"])')
fi

# Write .env for other services to consume
cat > .env.generated <<EOF
GITEA_URL=http://localhost:3000
GITEA_ADMIN_USER=${ADMIN_USER}
GITEA_ADMIN_PASS=${ADMIN_PASS}
GITEA_API_TOKEN=${TOKEN}
FORGE0_OPERATOR_TOKEN=${OPERATOR_TOKEN}
FORGE0_WEBHOOK_SECRET=${WEBHOOK_SECRET}
GITEA_OAUTH_CLIENT_ID=${OAUTH_CLIENT_ID}
GITEA_OAUTH_CLIENT_SECRET=${OAUTH_CLIENT_SECRET}
FORGE0_SESSION_SECRET=${SESSION_SECRET}
FORGE0_OAUTH_REDIRECT_URI=${OAUTH_REDIRECT_URI}
FORGE0_ALLOWED_USERS=${FORGE0_ALLOWED_USERS:-josh}
EOF
chmod 600 .env.generated

# Values exported from the operator's .env take precedence over --env-file in
# Compose. Force the freshly generated credentials into this setup process so
# a stale legacy GITEA_API_TOKEN cannot be injected into the recreated portal.
export GITEA_API_TOKEN="$TOKEN"
export FORGE0_OPERATOR_TOKEN="$OPERATOR_TOKEN"
export FORGE0_WEBHOOK_SECRET="$WEBHOOK_SECRET"
export GITEA_OAUTH_CLIENT_ID="$OAUTH_CLIENT_ID"
export GITEA_OAUTH_CLIENT_SECRET="$OAUTH_CLIENT_SECRET"
export FORGE0_SESSION_SECRET="$SESSION_SECRET"

CI_IMAGE="forge0-ci-base:py312-20260716"
RUNNER_IMAGE="docker.io/gitea/act_runner:0.2.13@sha256:8477d5b61b655caad4449888bae39f1f34bebd27db56cb15a62dccb3dcf3a944"

echo "==> Preparing immutable CI base image ${CI_IMAGE}..."
if ! docker image inspect "${CI_IMAGE}" >/dev/null 2>&1; then
  docker build --pull=false -f ci/Dockerfile -t "${CI_IMAGE}" portal
else
  echo "    Existing versioned image found; refusing to rebuild it during setup."
fi
CI_IMAGE_DIGEST=$(docker image inspect "${CI_IMAGE}" --format '{{index .RepoDigests 0}}')
if [ -z "${CI_IMAGE_DIGEST}" ]; then
  echo "ERROR: ${CI_IMAGE} has no content digest after build." >&2
  exit 1
fi
echo "    Locked runner image: ${CI_IMAGE_DIGEST}"

echo "==> Registering the dedicated Forge0 Actions runner..."
docker volume create forge0-runner-data >/dev/null
if ! docker run --rm --entrypoint="" -v forge0-runner-data:/data "${RUNNER_IMAGE}" \
  test -s /data/.runner; then
  RUNNER_TOKEN=$(curl -fsS -X POST -H "Authorization: token ${TOKEN}" \
    "http://localhost:3000/api/v1/admin/actions/runners/registration-token" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
  docker run --rm --entrypoint="" \
    --network forge0_default \
    -v forge0-runner-data:/data \
    -v "${PWD}/runner/config.yaml:/config.yaml:ro" \
    "${RUNNER_IMAGE}" \
    act_runner --config /config.yaml register --no-interactive \
      --instance http://gitea:3000/ \
      --token "${RUNNER_TOKEN}" \
      --name forge0-ci \
      --labels "forge0-ci:docker://${CI_IMAGE_DIGEST}"
else
  echo "    Runner registration already exists."
fi

echo ""
echo "============================================"

echo "==> Starting the complete core stack with the generated credentials..."
docker compose --env-file .env --env-file .env.generated up -d gitea searxng
docker compose --env-file .env --env-file .env.generated up -d --force-recreate --no-deps portal runner

SELF_REPO="${FORGE0_SELF_REPO:-agent/forge0}"
SELF_OWNER="${SELF_REPO%%/*}"
SELF_NAME="${SELF_REPO#*/}"
if curl -fsS -H "Authorization: token ${TOKEN}" \
  "http://localhost:3000/api/v1/repos/${SELF_OWNER}/${SELF_NAME}" >/dev/null 2>&1; then
  echo "==> Configuring self-extension webhook for ${SELF_REPO}..."
  HOOK_ID=$(curl -fsS -H "Authorization: token ${TOKEN}" \
    "http://localhost:3000/api/v1/repos/${SELF_OWNER}/${SELF_NAME}/hooks" | python3 -c '
import json
import sys

for hook in json.load(sys.stdin):
    if hook.get("config", {}).get("url") == "http://portal:3001/api/webhooks/gitea":
        print(hook["id"])
        break
' || true)
  if [ -z "$HOOK_ID" ]; then
    curl -fsS -X POST \
      -H "Authorization: token ${TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"type\":\"gitea\",\"name\":\"Forge0 self-extension\",\"active\":true,\"events\":[\"issues\"],\"config\":{\"url\":\"http://portal:3001/api/webhooks/gitea\",\"content_type\":\"json\",\"secret\":\"${WEBHOOK_SECRET}\"}}" \
      "http://localhost:3000/api/v1/repos/${SELF_OWNER}/${SELF_NAME}/hooks" >/dev/null
  fi

  LABEL_EXISTS=$(curl -fsS -H "Authorization: token ${TOKEN}" \
    "http://localhost:3000/api/v1/repos/${SELF_OWNER}/${SELF_NAME}/labels?limit=100" | python3 -c '
import json
import sys

print("yes" if any(label.get("name") == "agent:ready" for label in json.load(sys.stdin)) else "")
')
  if [ -z "$LABEL_EXISTS" ]; then
    curl -fsS -X POST \
      -H "Authorization: token ${TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{"name":"agent:ready","color":"#7c3aed","description":"Explicitly authorize a Forge0 draft-PR run"}' \
      "http://localhost:3000/api/v1/repos/${SELF_OWNER}/${SELF_NAME}/labels" >/dev/null
  fi
  TYPE_LABEL_EXISTS=$(curl -fsS -H "Authorization: token ${TOKEN}" \
    "http://localhost:3000/api/v1/repos/${SELF_OWNER}/${SELF_NAME}/labels?limit=100" | python3 -c '
import json
import sys

print("yes" if any(label.get("name") == "type:agent" for label in json.load(sys.stdin)) else "")
')
  if [ -z "$TYPE_LABEL_EXISTS" ]; then
    curl -fsS -X POST \
      -H "Authorization: token ${TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{"name":"type:agent","color":"7c3aed","description":"Change proposed by Forge0 self-extension"}' \
      "http://localhost:3000/api/v1/repos/${SELF_OWNER}/${SELF_NAME}/labels" >/dev/null
  fi
else
  echo "==> Self repository ${SELF_REPO} is not in Gitea yet; webhook setup skipped."
fi
echo "  forge0 Gitea ready"
echo "============================================"
echo "  URL:       http://localhost:3000"
echo "  User:      ${ADMIN_USER}"
echo "  Secrets:   stored in .env.generated (mode 600)"
echo "============================================"
