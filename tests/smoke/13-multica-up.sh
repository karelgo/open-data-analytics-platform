#!/usr/bin/env bash
# Smoke test 13 — Multica (case-tracking app for the WIA/WW/WAJONG flow).
#
# Checks:
#   1. multica-postgres StatefulSet pod Running
#   2. multica-backend Deployment Available
#   3. multica-frontend Deployment Available
#   4. multica-oauth2-proxy Deployment Available
#   5. Ingress multica.${PLATFORM_DOMAIN} exists with TLS
#   6. multica-backend secret has DATABASE_URL pointing at multica-postgres
#
# Skips elegantly if multica isn't deployed (e.g. user opted out).
set -euo pipefail

pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }
skip() { printf '  [SKIP] %s\n' "$*"; }
log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }

DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-${MODE:-k3d}}"
PLATFORM_DOMAIN="${PLATFORM_DOMAIN:-odap.local}"

NS=odap-platform

if ! kubectl -n "$NS" get deployment multica-backend >/dev/null 2>&1; then
  skip "multica-backend Deployment not in $NS — run 'make deploy-platform' (LAYERS includes 17-multica)"
  exit 0
fi

# 1. Postgres pod Ready
log "multica-postgres-0 Ready"
if kubectl -n "$NS" wait --for=condition=Ready pod/multica-postgres-0 --timeout=60s >/dev/null 2>&1; then
  pass "multica-postgres-0 Ready"
else
  fail "multica-postgres-0 niet Ready binnen 60s (mogelijk cluster pod-limit; zie 'kubectl describe pod')"
fi

# 2-4. Deployments Available
for d in multica-backend multica-frontend multica-oauth2-proxy; do
  log "Deployment $d Available"
  if kubectl -n "$NS" wait --for=condition=Available deployment/"$d" --timeout=60s >/dev/null 2>&1; then
    pass "$d Available"
  else
    fail "$d niet Available binnen 60s — check 'kubectl -n $NS get deploy $d'"
  fi
done

# 5. Ingress + TLS
expected_host="multica.${PLATFORM_DOMAIN}"
log "Ingress $expected_host"
ING_HOST=$(kubectl -n "$NS" get ingress multica -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || true)
ING_TLS=$(kubectl -n "$NS" get ingress multica -o jsonpath='{.spec.tls[0].secretName}' 2>/dev/null || true)
if [[ "$ING_HOST" == "$expected_host" && -n "$ING_TLS" ]]; then
  pass "ingress host=$ING_HOST tls-secret=$ING_TLS"
else
  fail "ingress multica niet correct (host=$ING_HOST tls=$ING_TLS, expected host=$expected_host)"
fi

# 6. DATABASE_URL in multica-backend secret references multica-postgres Service
log "Secret multica-backend has DATABASE_URL → multica-postgres"
DB_URL=$(kubectl -n "$NS" get secret multica-backend -o jsonpath='{.data.DATABASE_URL}' 2>/dev/null | base64 -d 2>/dev/null || true)
if echo "$DB_URL" | grep -q '@multica-postgres:5432/'; then
  pass "DATABASE_URL points at multica-postgres:5432"
else
  fail "DATABASE_URL malformed: '$DB_URL'"
fi

echo
pass "smoke 13-multica-up: alle checks groen"
