#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://localhost:8443}"
USERNAME="${SMOKE_USERNAME:-orgadmin}"
PASSWORD="${SMOKE_PASSWORD:-SecurePass1234}"

COOKIE_JAR="$(mktemp)"
trap 'rm -f "${COOKIE_JAR}"' EXIT

echo "Checking frontend shell"
front_code="$(curl -sk -o /tmp/harborops_frontend_smoke.html -w "%{http_code}" "${BASE_URL}/")"
if [[ "${front_code}" != "200" ]]; then
  echo "Frontend shell check failed with status ${front_code}" >&2
  exit 1
fi

echo "Fetching CSRF token"
csrf_json="$(curl -sk -c "${COOKIE_JAR}" "${BASE_URL}/api/auth/csrf/")"
csrf_token="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["csrfToken"])' "${csrf_json}")"

echo "Logging in via real backend"
login_payload="$(python3 -c 'import json,sys; print(json.dumps({"username":sys.argv[1],"password":sys.argv[2]}))' "${USERNAME}" "${PASSWORD}")"
login_code="$(curl -sk -o /tmp/harborops_login_smoke.json -w "%{http_code}" -b "${COOKIE_JAR}" -c "${COOKIE_JAR}" -H "Content-Type: application/json" -H "X-CSRFToken: ${csrf_token}" -X POST "${BASE_URL}/api/auth/login/" --data "${login_payload}")"
if [[ "${login_code}" != "200" ]]; then
  echo "Login smoke failed with status ${login_code}" >&2
  exit 1
fi

echo "Checking role-gated backend context"
roles_code="$(curl -sk -o /tmp/harborops_roles_smoke.json -w "%{http_code}" -b "${COOKIE_JAR}" "${BASE_URL}/api/access/me/roles/")"
if [[ "${roles_code}" != "200" ]]; then
  echo "Role context smoke failed with status ${roles_code}" >&2
  exit 1
fi

echo "Running real write action"
favorite_payload='{"kind":"trip","reference_id":"smoke-trip"}'
favorite_code="$(curl -sk -o /tmp/harborops_favorite_smoke.json -w "%{http_code}" -b "${COOKIE_JAR}" -H "Content-Type: application/json" -H "X-CSRFToken: ${csrf_token}" -X POST "${BASE_URL}/api/auth/favorites/" --data "${favorite_payload}")"
if [[ "${favorite_code}" != "201" && "${favorite_code}" != "409" ]]; then
  echo "Write-action smoke failed with status ${favorite_code}" >&2
  exit 1
fi

echo "Frontend-backend smoke test passed"
