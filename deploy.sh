#!/usr/bin/env sh
set -e

if [ ! -f ".env" ]; then
  echo "Missing .env file in project root"
  exit 1
fi

echo "Building and starting InfraGIS..."
docker compose -f docker-compose.prod.yml up -d --build

echo "Waiting for health endpoint..."
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
    echo "InfraGIS is healthy"
    exit 0
  fi
  sleep 3
done

echo "Health check failed"
docker compose -f docker-compose.prod.yml ps
exit 1
