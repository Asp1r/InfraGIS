#!/usr/bin/env bash
set -euo pipefail

# InfraGIS remote deployment over SSH with rollback.
# Usage:
#   ./scripts/deploy-remote.sh \
#     --host 1.2.3.4 \
#     --user deploy \
#     --project-dir /opt/infragis \
#     --branch master \
#     --key ~/.ssh/id_rsa

HOST=""
USER_NAME=""
PROJECT_DIR=""
BRANCH="master"
SSH_KEY=""
SSH_PORT="22"
HEALTH_URL="http://127.0.0.1/health"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --user)
      USER_NAME="$2"
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --key)
      SSH_KEY="$2"
      shift 2
      ;;
    --port)
      SSH_PORT="$2"
      shift 2
      ;;
    --health-url)
      HEALTH_URL="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      exit 1
      ;;
  esac
done

if [[ -z "$HOST" || -z "$USER_NAME" || -z "$PROJECT_DIR" ]]; then
  echo "Missing required args: --host, --user, --project-dir"
  exit 1
fi

SSH_OPTS=("-p" "$SSH_PORT" "-o" "StrictHostKeyChecking=accept-new")
if [[ -n "$SSH_KEY" ]]; then
  SSH_OPTS+=("-i" "$SSH_KEY")
fi

REMOTE="${USER_NAME}@${HOST}"

echo "Deploying to ${REMOTE}:${PROJECT_DIR} (branch=${BRANCH})"

ssh "${SSH_OPTS[@]}" "$REMOTE" "bash -s -- \"${PROJECT_DIR}\" \"${BRANCH}\" \"${HEALTH_URL}\"" <<'EOF'
set -euo pipefail

PROJECT_DIR="$1"
BRANCH="$2"
HEALTH_URL="$3"

cd "$PROJECT_DIR"

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env is missing in $PROJECT_DIR"
  exit 1
fi

if [[ ! -d ".git" ]]; then
  echo "ERROR: $PROJECT_DIR is not a git repository"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed on server"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is not available on server"
  exit 1
fi

CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo "Current commit: $CURRENT_COMMIT"

git fetch --all --prune
git checkout "$BRANCH" >/dev/null 2>&1 || git checkout -B "$BRANCH" "origin/$BRANCH"
git pull --ff-only origin "$BRANCH"

NEW_COMMIT=$(git rev-parse --short HEAD)
echo "Target commit: $NEW_COMMIT"

set +e
docker compose -f docker-compose.prod.yml up -d --build
DEPLOY_EXIT=$?
set -e

if [[ $DEPLOY_EXIT -ne 0 ]]; then
  echo "Deploy step failed, rollback to $CURRENT_COMMIT"
  git checkout "$CURRENT_COMMIT"
  docker compose -f docker-compose.prod.yml up -d --build
  git checkout "$BRANCH" >/dev/null 2>&1 || true
  exit 1
fi

for i in $(seq 1 40); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Health check passed"
    exit 0
  fi
  sleep 3
done

echo "Health check failed, rollback to $CURRENT_COMMIT"
git checkout "$CURRENT_COMMIT"
docker compose -f docker-compose.prod.yml up -d --build
git checkout "$BRANCH" >/dev/null 2>&1 || true
exit 1
EOF

echo "Deploy completed successfully"
