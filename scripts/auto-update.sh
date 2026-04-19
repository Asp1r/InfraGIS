#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/infragis}"
BRANCH="${BRANCH:-master}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/health}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
LOG_PREFIX="${LOG_PREFIX:-[infragis-auto-update]}"

echo "$LOG_PREFIX Starting auto-update"
cd "$PROJECT_DIR"

if [[ ! -f ".env" ]]; then
  echo "$LOG_PREFIX ERROR: .env is missing"
  exit 1
fi

if [[ ! -d ".git" ]]; then
  echo "$LOG_PREFIX ERROR: git repository is missing"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "$LOG_PREFIX ERROR: docker is not installed"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "$LOG_PREFIX ERROR: docker compose plugin is not available"
  exit 1
fi

CURRENT_COMMIT="$(git rev-parse --short HEAD)"
echo "$LOG_PREFIX Current commit: $CURRENT_COMMIT"

git fetch --all --prune
git checkout "$BRANCH" >/dev/null 2>&1 || git checkout -B "$BRANCH" "origin/$BRANCH"
git pull --ff-only origin "$BRANCH"

NEW_COMMIT="$(git rev-parse --short HEAD)"
echo "$LOG_PREFIX Target commit: $NEW_COMMIT"

set +e
docker compose -f "$COMPOSE_FILE" up -d --build
DEPLOY_EXIT=$?
set -e

if [[ $DEPLOY_EXIT -ne 0 ]]; then
  echo "$LOG_PREFIX Deploy failed, rollback to $CURRENT_COMMIT"
  git checkout "$CURRENT_COMMIT"
  docker compose -f "$COMPOSE_FILE" up -d --build
  git checkout "$BRANCH" >/dev/null 2>&1 || true
  exit 1
fi

for _ in $(seq 1 40); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "$LOG_PREFIX Health check passed"
    exit 0
  fi
  sleep 3
done

echo "$LOG_PREFIX Health check failed, rollback to $CURRENT_COMMIT"
git checkout "$CURRENT_COMMIT"
docker compose -f "$COMPOSE_FILE" up -d --build
git checkout "$BRANCH" >/dev/null 2>&1 || true
exit 1
