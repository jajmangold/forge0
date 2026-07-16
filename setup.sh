#!/usr/bin/env bash
# forge0-setup.sh — Bootstrap admin user + API token after first `docker compose up -d`.
# Run once: ./setup.sh
# Idempotent: safe to re-run (will just print existing token).
set -euo pipefail
cd "$(dirname "$0")"

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

# Create an API token (check for existing one first)
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
  # Token may already exist — try to get it via the API
  echo "    Token may already exist. Listing tokens..."
  TOKEN=$(docker exec -u git forge0 \
    curl -s -u "${ADMIN_USER}:${ADMIN_PASS}" \
      http://localhost:3000/api/v1/users/${ADMIN_USER}/tokens \
    2>/dev/null | python3 -c "
import sys, json
try:
    tokens = json.load(sys.stdin)
    for t in tokens:
        if t.get('name') == 'forge0-agent':
            print(t.get('sha1', ''))
            break
except: pass
" 2>/dev/null || true)
fi

if [ -z "$TOKEN" ]; then
  echo "WARN: Could not get API token. Create one manually:" >&2
  echo "  docker compose exec gitea gitea admin user generate-access-token --username ${ADMIN_USER} --token-name forge0-agent --scopes all" >&2
  exit 1
fi

# Write .env for other services to consume
cat > .env.generated <<EOF
GITEA_URL=http://localhost:3000
GITEA_ADMIN_USER=${ADMIN_USER}
GITEA_ADMIN_PASS=${ADMIN_PASS}
GITEA_API_TOKEN=${TOKEN}
EOF
chmod 600 .env.generated

echo ""
echo "============================================"
echo "  forge0 Gitea ready"
echo "============================================"
echo "  URL:       http://localhost:3000"
echo "  User:      ${ADMIN_USER}"
echo "  Pass:      ${ADMIN_PASS}"
echo "  API Token: ${TOKEN}"
echo "  .env file: .env.generated"
echo "============================================"
