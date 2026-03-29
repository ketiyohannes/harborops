#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.yml"
HEALTH_URL="https://localhost:8443/api/health/"

echo "[1/6] Resetting Docker stack"
docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans || true

echo "[2/6] Starting Docker services"
docker compose -f "${COMPOSE_FILE}" up -d --build

echo "[3/6] Waiting for HTTPS health endpoint"
health_ok=0
for attempt in $(seq 1 60); do
  if curl -fsSk "${HEALTH_URL}" > /dev/null; then
    health_ok=1
    break
  fi
  sleep 2
done

if [[ "${health_ok}" -ne 1 ]]; then
  echo "Health check failed after retries" >&2
  docker compose -f "${COMPOSE_FILE}" logs backend proxy
  exit 1
fi

echo "[4/6] Running backend end-to-end suite"
docker compose -f "${COMPOSE_FILE}" exec -T backend \
  python manage.py test tests.test_e2e_suite -v 1

echo "[5/6] Running frontend test suite"
docker compose -f "${COMPOSE_FILE}" exec -T frontend npm run test:run

echo "[6/6] Running frontend production build"
docker compose -f "${COMPOSE_FILE}" exec -T frontend npm run build

echo "All Docker end-to-end tests passed"
