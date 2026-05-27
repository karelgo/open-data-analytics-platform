#!/usr/bin/env bash
# End-to-end integration test voor de OM→Keycloak access-bridge (ADR-0008).
#
# Flow (allemaal via API, geen UI nodig):
#   1. Pick een Trino-table asset uit OM (default: een silver/gold mart).
#   2. POST een Task type=RequestDescription, met "Request Access ..." in
#      de message, assignees = data.steward.
#   3. PATCH de Task naar Resolved/Approved (via admin-token; in productie
#      doet de assignee dit).
#   4. Wacht tot OM het taskResolved event publiceert + de bridge het
#      verwerkt.
#   5. Verifieer dat user X de realm-role `data_access:<cat>.<schema>` in
#      Keycloak heeft.
#
# Vereist: kubectl-exec/port-forward in een gezonde k3d/AKS-cluster
# (Keycloak in odap-auth, OM in odap-meta, bridge in odap-platform). Run via:
#
#   bash tests/integration/om-bridge-e2e.sh
#
# Niet onderdeel van `make smoke` — kost ~30s en muteert state.

set -euo pipefail

OM_NS="${OM_NS:-odap-meta}"
KC_NS="${KC_NS:-odap-auth}"
BRIDGE_NS="${BRIDGE_NS:-odap-platform}"
REQUESTER="${E2E_REQUESTER:-researcher}"
ASSIGNEE="${E2E_ASSIGNEE:-data.steward}"
ASSET_FQN="${E2E_ASSET_FQN:-trino.gold.uc05_customer_360.mart_uc05_customer_360}"
EXPECTED_ROLE="data_access:gold.uc05_customer_360"
OM_PF_PORT="${OM_PF_PORT:-18586}"
KC_PF_PORT="${KC_PF_PORT:-18081}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }
skip() { printf '\033[1;33mSKIP\033[0m %s\n' "$*"; exit 0; }

# Cleanup port-forwards on any exit.
PIDS=()
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT

# --- 0. Pre-flight ------------------------------------------------------
log "Bridge Deployment Ready?"
kubectl -n "$BRIDGE_NS" get deploy om-access-bridge >/dev/null 2>&1 \
  || skip "om-access-bridge niet gedeployed — run 'make deploy-om-bridge' eerst."
kubectl -n "$BRIDGE_NS" rollout status deploy/om-access-bridge --timeout=30s >/dev/null 2>&1 \
  || fail "bridge Deployment niet Ready"
pass "bridge Ready"

log "Port-forwards openen (OM=$OM_PF_PORT, KC=$KC_PF_PORT)"
kubectl -n "$OM_NS" port-forward svc/openmetadata "$OM_PF_PORT":8585 >/tmp/e2e-om-pf.log 2>&1 &
PIDS+=($!)
kubectl -n "$KC_NS" port-forward svc/keycloak "$KC_PF_PORT":80 >/tmp/e2e-kc-pf.log 2>&1 &
PIDS+=($!)
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -fsS --max-time 2 "http://127.0.0.1:${OM_PF_PORT}/api/v1/system/version" >/dev/null 2>&1 \
    && curl -fsS --max-time 2 "http://127.0.0.1:${KC_PF_PORT}/realms/master" >/dev/null 2>&1 \
    && break
  sleep 1
done
curl -fsS --max-time 5 "http://127.0.0.1:${OM_PF_PORT}/api/v1/system/version" >/dev/null 2>&1 \
  || skip "OM port-forward niet bereikbaar (kubelet 502?) — $(tail -3 /tmp/e2e-om-pf.log)"
curl -fsS --max-time 5 "http://127.0.0.1:${KC_PF_PORT}/realms/master" >/dev/null 2>&1 \
  || skip "Keycloak port-forward niet bereikbaar — $(tail -3 /tmp/e2e-kc-pf.log)"
pass "port-forwards bereikbaar"

OM_BASE="http://127.0.0.1:${OM_PF_PORT}"
KC_BASE="http://127.0.0.1:${KC_PF_PORT}"

# --- 1. Tokens ---------------------------------------------------------
OM_TOKEN=$(kubectl -n "$OM_NS" get secret openmetadata-admin -o jsonpath='{.data.jwtToken}' | base64 -d)
[ -n "$OM_TOKEN" ] || fail "geen OM jwtToken in openmetadata-admin secret"

KC_TOKEN=$(curl -fsS -d "client_id=admin-cli" -d "username=kcadmin" -d "password=odap-dev-only-CHANGE-ME" -d "grant_type=password" \
  "${KC_BASE}/realms/master/protocol/openid-connect/token" | sed 's/.*access_token":"\([^"]*\)".*/\1/')
[ -n "$KC_TOKEN" ] || fail "Keycloak admin-token niet verkregen"

# --- 2. Asset bestaat in OM? -------------------------------------------
log "Asset ${ASSET_FQN} bestaat in OM?"
ASSET_ID=$(curl -sS -H "Authorization: Bearer ${OM_TOKEN}" \
  "${OM_BASE}/api/v1/tables/name/${ASSET_FQN}" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4 || true)
if [ -z "$ASSET_ID" ]; then
  skip "asset ${ASSET_FQN} niet gevonden — Trino-ingestion nog niet gelopen?"
fi
pass "asset id=${ASSET_ID}"

# --- 3. Snapshot huidige rollen van requester --------------------------
log "Huidige Keycloak-roles voor ${REQUESTER}"
USER_ID=$(curl -fsS -H "Authorization: Bearer ${KC_TOKEN}" \
  "${KC_BASE}/admin/realms/odap/users?username=${REQUESTER}&exact=true" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
[ -n "$USER_ID" ] || fail "user ${REQUESTER} niet gevonden in Keycloak"
BEFORE=$(curl -fsS -H "Authorization: Bearer ${KC_TOKEN}" \
  "${KC_BASE}/admin/realms/odap/users/${USER_ID}/role-mappings/realm" | grep -oE '"name":"[^"]+"' | tr -d '"' | tr '\n' ' ')
if echo "$BEFORE" | grep -q "name:${EXPECTED_ROLE}"; then
  log "  rol bestaat al — verwijder eerst voor schone test"
  ROLE_OBJ=$(curl -fsS -H "Authorization: Bearer ${KC_TOKEN}" "${KC_BASE}/admin/realms/odap/roles/${EXPECTED_ROLE}")
  ROLE_ID=$(echo "$ROLE_OBJ" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
  curl -sS -o /dev/null -X DELETE -H "Authorization: Bearer ${KC_TOKEN}" -H 'Content-Type: application/json' \
    "${KC_BASE}/admin/realms/odap/users/${USER_ID}/role-mappings/realm" \
    -d "[{\"id\":\"$ROLE_ID\",\"name\":\"$EXPECTED_ROLE\"}]"
fi
pass "snapshot genomen"

# --- 4. Maak Task via OM API ------------------------------------------
log "POST nieuwe Task (Request Access) op asset"
THREAD_BODY=$(cat <<EOF
{
  "from": "${REQUESTER}",
  "message": "Request Access — gebruiker ${REQUESTER}, doel klantcontact. E2E-test.",
  "about": "<#E::table::${ASSET_FQN}>",
  "type": "Task",
  "task": {
    "type": "RequestDescription",
    "assignees": [{"type": "user", "name": "${ASSIGNEE}"}]
  }
}
EOF
)
THREAD_RESP=$(curl -sS -w "\n%{http_code}" -X POST -H "Authorization: Bearer ${OM_TOKEN}" \
  -H 'Content-Type: application/json' \
  "${OM_BASE}/api/v1/feed" -d "$THREAD_BODY")
THREAD_STATUS=$(echo "$THREAD_RESP" | tail -1)
THREAD_JSON=$(echo "$THREAD_RESP" | sed '$d')
if [ "$THREAD_STATUS" != "201" ] && [ "$THREAD_STATUS" != "200" ]; then
  fail "task POST=${THREAD_STATUS} body=$(echo "$THREAD_JSON" | head -c 300)"
fi
TASK_ID=$(echo "$THREAD_JSON" | grep -oE '"id":[[:space:]]*[0-9]+' | head -1 | grep -oE '[0-9]+')
THREAD_ID=$(echo "$THREAD_JSON" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
pass "Task aangemaakt (taskId=${TASK_ID}, threadId=${THREAD_ID})"

# --- 5. Resolve de Task ------------------------------------------------
log "Resolve Task ${TASK_ID} met resolution=approved"
RESOLVE_STATUS=$(curl -sS -o /tmp/resolve.json -w '%{http_code}' -X PUT \
  -H "Authorization: Bearer ${OM_TOKEN}" -H 'Content-Type: application/json' \
  "${OM_BASE}/api/v1/feed/tasks/${TASK_ID}/resolve" \
  -d "{\"newValue\":\"E2E approval\"}")
[ "$RESOLVE_STATUS" = "200" ] || fail "task resolve=${RESOLVE_STATUS} body=$(cat /tmp/resolve.json | head -c 300)"
pass "Task resolved"

# --- 6. Wacht op bridge → Keycloak rol --------------------------------
log "Polling: ${EXPECTED_ROLE} verschijnt in Keycloak-roles van ${REQUESTER}"
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  AFTER=$(curl -fsS -H "Authorization: Bearer ${KC_TOKEN}" \
    "${KC_BASE}/admin/realms/odap/users/${USER_ID}/role-mappings/realm" | grep -oE '"name":"[^"]+"' | tr -d '"' | tr '\n' ' ')
  if echo "$AFTER" | grep -q "name:${EXPECTED_ROLE}"; then
    pass "grant aangekomen na ${i} polls (~$((i*2))s) — rol ${EXPECTED_ROLE} aanwezig"
    echo
    pass "e2e: alle stappen groen"
    exit 0
  fi
  sleep 2
done

log "Laatste 30 bridge log-regels:"
kubectl -n "$BRIDGE_NS" logs deploy/om-access-bridge --tail=30
fail "rol ${EXPECTED_ROLE} verscheen NIET binnen 24s — bridge heeft event niet (correct) verwerkt"
