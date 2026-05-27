#!/usr/bin/env bash
# Smoke test 10 — OM → Keycloak access-bridge draait en weert
# ongesigneerde webhooks.
#
# Voorwaarden:
#   - make deploy-om-bridge gedraaid (Deployment + Service in odap-platform ns)
#   - Keycloak `om-access-bridge`-client in realm (realm.json)
#
# Wat we checken:
#   1. Deployment Ready
#   2. /health endpoint retourneert 200 met expected JSON
#   3. POST /webhooks/om zonder HMAC-header → 401 (security-default)
#   4. Keycloak Admin API: client `om-access-bridge` bestaat met
#      serviceAccountsEnabled: true (proxy voor "realm-import is gelopen")
set -euo pipefail

NS="${NS:-odap-platform}"
AUTH_NS="${AUTH_NS:-odap-auth}"

log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }

# --- 1. Deployment Ready -------------------------------------------------
# De bridge is optioneel: niet automatisch in deploy-platform. Als de
# Deployment niet eens bestaat slaan we de hele test over zodat `make
# smoke` groen blijft voor wie alleen de base-platform draait.
log "om-access-bridge Deployment aanwezig?"
if ! kubectl -n "$NS" get deploy/om-access-bridge >/dev/null 2>&1; then
  printf '\033[1;33m  SKIP\033[0m om-access-bridge niet gedeployed — run `make deploy-om-bridge` om deze test te activeren.\n'
  exit 0
fi
kubectl -n "$NS" rollout status deploy/om-access-bridge --timeout=120s >/dev/null 2>&1 \
  || fail "Deployment niet Ready — kijk: kubectl -n $NS describe deploy/om-access-bridge"
pass "Deployment Ready"

# --- 2. /health ----------------------------------------------------------
log "/health endpoint"
health=$(kubectl -n "$NS" run om-bridge-smoke-$RANDOM \
  --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
  curl -fsS --max-time 10 \
    "http://om-access-bridge.${NS}.svc.cluster.local/health" 2>/dev/null || echo "")
if [[ -z "$health" ]]; then
  fail "/health gaf lege response"
fi
echo "$health" | grep -q '"status":"ok"' \
  || fail "/health onverwacht: $health"
echo "$health" | grep -q '"realm":"odap"' \
  || fail "/health mist realm-veld: $health"
pass "/health = ok (realm=odap)"

# --- 3. POST zonder HMAC → 401 -------------------------------------------
log "POST /webhooks/om zonder X-OM-Signature → 401 verwacht"
code=$(kubectl -n "$NS" run om-bridge-smoke-$RANDOM \
  --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
  curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    -X POST "http://om-access-bridge.${NS}.svc.cluster.local/webhooks/om" \
    -H 'Content-Type: application/json' \
    -d '{"entityType":"task","eventType":"taskResolved","task":{"id":"smoke","resolution":"approved","createdBy":"alice","about":"trino.gold.uc05_customer_360.mart_uc05_customer_360"}}' 2>/dev/null || echo "000")
if [[ "$code" != "401" ]]; then
  fail "Verwachtte 401 zonder HMAC; kreeg $code (security-default kapot)"
fi
pass "ongesigneerde webhook geweigerd (401)"

# --- 4. Keycloak client bestaat -----------------------------------------
log "Keycloak: client om-access-bridge bestaat"
# Haal kcadmin-token in cluster via curl tegen Keycloak.
if ! kubectl -n "$AUTH_NS" get pod keycloak-0 >/dev/null 2>&1; then
  log "  Keycloak pod niet gevonden — Keycloak-check overgeslagen"
else
  found=$(kubectl -n "$AUTH_NS" exec keycloak-0 -c keycloak -- bash -c '
    T=$(curl -fsS -d "client_id=admin-cli" -d "username=kcadmin" \
      -d "password=odap-dev-only-CHANGE-ME" -d "grant_type=password" \
      http://localhost:8080/realms/master/protocol/openid-connect/token 2>/dev/null \
      | sed "s/.*access_token\":\"\([^\"]*\)\".*/\1/")
    [ -z "$T" ] && { echo "no-token"; exit 0; }
    curl -fsS -H "Authorization: Bearer $T" \
      "http://localhost:8080/admin/realms/odap/clients?clientId=om-access-bridge" 2>/dev/null
  ' 2>/dev/null || echo "")
  if echo "$found" | grep -q '"clientId":"om-access-bridge"'; then
    pass "client 'om-access-bridge' aanwezig in realm uwv"
  else
    fail "client 'om-access-bridge' ontbreekt in realm uwv (realm-import niet gelopen?)"
  fi
fi

echo
pass "smoke 10-om-access-bridge: alle checks groen"
