#!/usr/bin/env bash
# Smoke test 02 — Trino + OPA staan op en accepteren een eenvoudige query.
#
# Required: fase 0 + 1 + 2 + 3 zijn applied.
#
# Stappen:
#   1. TrinoCluster + OpaCluster pods Ready
#   2. OPA-bundle ConfigMap aanwezig met juiste label
#   3. OPA decision-endpoint antwoordt op `data.trino.allow` (in-cluster curl)
#   4. SHOW CATALOGS via static-auth user retourneert minimaal: bronze, silver, gold, sensitive
#   5. SELECT 1 werkt
set -euo pipefail

NS="${NS:-odap-platform}"
SMOKE_USER="${SMOKE_USER:-smoketest}"
SMOKE_PASSWORD="${SMOKE_PASSWORD:-odap-dev-only-CHANGE-ME-Smoke2026}"

log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Pods Ready
log "Trino-coordinator + worker Ready"
kubectl -n "$NS" rollout status statefulset/trino-coordinator-default --timeout=5m >/dev/null \
  || fail "Trino-coordinator niet Ready"
kubectl -n "$NS" rollout status statefulset/trino-worker-default --timeout=5m >/dev/null \
  || fail "Trino-worker niet Ready"
pass "Trino-coordinator + worker pods Ready"

log "OPA cluster Ready"
kubectl -n "$NS" rollout status daemonset/opa-server-default --timeout=5m >/dev/null 2>&1 \
  || kubectl -n "$NS" rollout status statefulset/opa-server-default --timeout=5m >/dev/null \
  || fail "OPA niet Ready (geen daemonset of statefulset opa-server-default)"
pass "OPA pods Ready"

# 2. Bundle-ConfigMap aanwezig + correct gelabeld
log "OPA-bundle ConfigMap"
if ! kubectl -n "$NS" get configmap opa-trino-bundle >/dev/null 2>&1; then
  fail "ConfigMap opa-trino-bundle ontbreekt"
fi
if [[ "$(kubectl -n "$NS" get configmap opa-trino-bundle -o jsonpath='{.metadata.labels.opa\.stackable\.tech/bundle}')" != "true" ]]; then
  fail "Label opa.stackable.tech/bundle=true ontbreekt op ConfigMap"
fi
pass "ConfigMap opa-trino-bundle correct gelabeld"

# 3. OPA decision endpoint
log "OPA decision endpoint /v1/data/trino/allow"
opa_result=$(kubectl -n "$NS" run opa-smoke-$RANDOM \
  --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
  curl -fsS --max-time 10 \
    -H 'Content-Type: application/json' \
    -X POST "http://opa-server.${NS}.svc.cluster.local:8081/v1/data/trino/allow" \
    -d '{"input":{"context":{"identity":{"user":"smoketest"}},"action":{"operation":"ExecuteQuery"}}}' \
  2>/dev/null || true)
if echo "$opa_result" | grep -q '"result": *true'; then
  pass "OPA antwoordt allow:true voor authenticated user"
else
  fail "OPA decision response: $opa_result"
fi

# Anonymous user → moet deny krijgen
opa_anon=$(kubectl -n "$NS" run opa-smoke-anon-$RANDOM \
  --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
  curl -fsS --max-time 10 \
    -H 'Content-Type: application/json' \
    -X POST "http://opa-server.${NS}.svc.cluster.local:8081/v1/data/trino/allow" \
    -d '{"input":{"context":{"identity":{"user":""}},"action":{"operation":"ExecuteQuery"}}}' \
  2>/dev/null || true)
if echo "$opa_anon" | grep -q '"result": *false'; then
  pass "OPA antwoordt allow:false voor anonymous user (default-deny werkt)"
else
  fail "OPA antwoord op anonymous niet zoals verwacht: $opa_anon"
fi

# Stackable 26.3 trino-server image bundles geen CLI meer; query via REST
# (stdin-streamed python helper, gebruikt alleen stdlib in de trino-pod).
# Trino-cluster heeft `authentication: []` (geen password-auth), dus alleen
# X-Trino-User; geen TRINO_PASSWORD doorgeven.
TRINO_HELPER="$(dirname "$0")/_trino_query.py"
trino_exec() {
  kubectl -n "$NS" exec -i statefulset/trino-coordinator-default -c trino -- \
    env TRINO_USER="$SMOKE_USER" TRINO_SERVER="https://localhost:8443" \
    python3 - "$1" <"$TRINO_HELPER"
}

# 4. SHOW CATALOGS via REST
log "SHOW CATALOGS via static-auth"
catalog_out=$(trino_exec "SHOW CATALOGS" 2>&1 || true)

for c in bronze silver gold sensitive; do
  if echo "$catalog_out" | grep -qx "$c"; then
    pass "catalog $c aanwezig"
  else
    fail "catalog $c ontbreekt — output:\n$catalog_out"
  fi
done

# 5. SELECT 1
log "SELECT 1 via static-auth"
select_out=$(trino_exec "SELECT 1" 2>&1 || true)
if echo "$select_out" | grep -qx '1'; then
  pass "SELECT 1 → 1"
else
  fail "SELECT 1 onverwacht: $select_out"
fi

echo
pass "smoke 02-trino-query: alle checks groen"
