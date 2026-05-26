#!/usr/bin/env bash
# Idempotent setup van de om-access-bridge Keycloak-client + service-account
# roles. Gebruikt port-forward + admin-API; geen Keycloak-restart nodig.
#
# Achtergrond: Keycloak's realm-import draait met strategy IGNORE_EXISTING op
# subsequent boots. Nieuwe clients die we toevoegen aan realm.json komen
# pas in een gereset-cluster mee — niet bij re-applies. Dit script dicht
# dat gat consistent dichter bij de make-target.
#
# Idempotent: bestaande client + bestaande role-assignments → exit 0 zonder
# wijzigingen.

set -euo pipefail

NS="${KC_NS:-odap-auth}"
KC_ADMIN_USER="${KC_ADMIN_USER:-kcadmin}"
KC_ADMIN_PASSWORD="${KC_ADMIN_PASSWORD:-odap-dev-only-CHANGE-ME}"
CLIENT_ID="om-access-bridge"
CLIENT_SECRET="${OM_BRIDGE_KC_SECRET:-odap-dev-only-CHANGE-ME-om-access-bridge-secret}"
PF_PORT="${PF_PORT:-18080}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

PF_PID=
cleanup() { [ -n "$PF_PID" ] && kill $PF_PID 2>/dev/null || true; }
trap cleanup EXIT

log "Port-forward keycloak → 127.0.0.1:${PF_PORT}"
kubectl -n "$NS" port-forward svc/keycloak ${PF_PORT}:80 >/tmp/kc-pf.log 2>&1 &
PF_PID=$!
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -fsS --max-time 2 "http://127.0.0.1:${PF_PORT}/realms/master" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS --max-time 5 "http://127.0.0.1:${PF_PORT}/realms/master" >/dev/null 2>&1 \
  || fail "port-forward niet bereikbaar — check kubelet health: $(tail -3 /tmp/kc-pf.log)"

log "Admin-login als ${KC_ADMIN_USER}"
T=$(curl -fsS -d "client_id=admin-cli" -d "username=${KC_ADMIN_USER}" -d "password=${KC_ADMIN_PASSWORD}" -d "grant_type=password" \
  "http://127.0.0.1:${PF_PORT}/realms/master/protocol/openid-connect/token" | sed 's/.*access_token":"\([^"]*\)".*/\1/')
[ -n "$T" ] || fail "admin-token lookup faalde"
A="Authorization: Bearer $T"
KC="http://127.0.0.1:${PF_PORT}"

log "Client ${CLIENT_ID} aanwezig?"
CLIENT_UUID=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients?clientId=${CLIENT_ID}" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
if [ -z "$CLIENT_UUID" ]; then
  log "  client ontbreekt — POST /admin/realms/odap/clients"
  STATUS=$(curl -sS -o /tmp/c.json -w '%{http_code}' -X POST -H "$A" -H 'Content-Type: application/json' \
    "$KC/admin/realms/odap/clients" -d "{
      \"clientId\":\"${CLIENT_ID}\",
      \"name\":\"OpenMetadata Access Bridge (service account)\",
      \"description\":\"Service-account voor de om-access-bridge; kent realm-roles data_access:<catalog>.<schema> toe na approval in OpenMetadata. Zie ADR-0008.\",
      \"enabled\":true,
      \"protocol\":\"openid-connect\",
      \"publicClient\":false,
      \"secret\":\"${CLIENT_SECRET}\",
      \"standardFlowEnabled\":false,
      \"directAccessGrantsEnabled\":false,
      \"serviceAccountsEnabled\":true,
      \"redirectUris\":[],
      \"webOrigins\":[],
      \"defaultClientScopes\":[\"profile\",\"roles\"],
      \"fullScopeAllowed\":true,
      \"attributes\":{\"use.refresh.tokens\":\"false\"}
    }")
  [ "$STATUS" = "201" ] || fail "client POST=$STATUS body=$(cat /tmp/c.json)"
  CLIENT_UUID=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients?clientId=${CLIENT_ID}" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
  pass "client aangemaakt (uuid=$CLIENT_UUID)"
else
  pass "client al aanwezig (uuid=$CLIENT_UUID)"
fi

SA_USER_ID=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients/$CLIENT_UUID/service-account-user" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
[ -n "$SA_USER_ID" ] || fail "service-account user-id niet gevonden"

RM_UUID=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients?clientId=realm-management" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
[ -n "$RM_UUID" ] || fail "realm-management client niet gevonden"

HAVE=$(curl -fsS -H "$A" "$KC/admin/realms/odap/users/$SA_USER_ID/role-mappings/clients/$RM_UUID" | grep -oE '"name":"[^"]+"' | tr -d '"' | tr '\n' ' ')

# Required roles, expanded:
# - manage-users : look up + add realm-roles to users (the granted user)
# - view-users   : pre-check / search for the target user
# - view-realm   : list realm-level roles when ensuring the grant-role exists
# - manage-realm : CREATE the `data_access:<catalog>.<schema>` realm-role
#                  when it doesn't exist yet (first grant of a new catalog/
#                  schema combo). Without this the bridge returns 403 on
#                  POST /admin/realms/odap/roles.
REQUIRED_ROLES=(manage-users view-users view-realm manage-realm)
log "Service-account roles diff'en met {${REQUIRED_ROLES[*]}}"
NEED=0
ROLES_JSON='['
SEP=''
for r in "${REQUIRED_ROLES[@]}"; do
  echo "$HAVE" | grep -q "name:$r" && continue
  RID=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients/$RM_UUID/roles/$r" | grep -oE '"id":"[^"]+"' | head -1 | cut -d'"' -f4)
  [ -n "$RID" ] || { log "  warn: role $r niet vindbaar in realm-management"; continue; }
  ROLES_JSON="${ROLES_JSON}${SEP}{\"id\":\"$RID\",\"name\":\"$r\",\"containerId\":\"$RM_UUID\",\"clientRole\":true}"
  SEP=','
  NEED=$((NEED+1))
done
ROLES_JSON="${ROLES_JSON}]"

if [ "$NEED" -gt 0 ]; then
  STATUS=$(curl -sS -o /tmp/r.json -w '%{http_code}' -X POST -H "$A" -H 'Content-Type: application/json' \
    "$KC/admin/realms/odap/users/$SA_USER_ID/role-mappings/clients/$RM_UUID" -d "$ROLES_JSON")
  [ "$STATUS" = "204" ] || fail "role-assign HTTP=$STATUS body=$(cat /tmp/r.json)"
  pass "$NEED role(s) toegekend aan service-account"
else
  pass "alle ${#REQUIRED_ROLES[@]} service-account roles al toegekend"
fi

# ---------------------------------------------------------------------------
# Client-roles protocol-mapper
#
# Background: this realm overrides the standard `roles` client-scope so it
# only contains a *realm roles* mapper (claim: `roles`). There is no
# *client roles* mapper, so the bridge's SA token does NOT carry
# `resource_access.realm-management.roles` even with fullScopeAllowed=true
# and the realm-management roles correctly assigned to the SA user.
# Result without this step: every admin-API call returns 403.
#
# We add a per-client mapper on om-access-bridge that exposes the
# realm-management client roles in `resource_access.realm-management.roles`,
# matching what Keycloak's default `roles` scope would have done.
# ---------------------------------------------------------------------------
MAPPER_NAME="realm-management-roles"
# `|| true` masks pipefail + grep-no-match: under `set -o pipefail`, a
# non-matching grep returns 1 which would otherwise abort the script via
# `set -e`. We want "no mapper" to be a normal control-flow signal.
HAVE_MAPPER=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients/$CLIENT_UUID/protocol-mappers/models" \
  | { grep -oE "\"name\":\"${MAPPER_NAME}\"" || true; } | head -1)
if [ -z "$HAVE_MAPPER" ]; then
  log "Add client-roles protocol-mapper voor realm-management op ${CLIENT_ID}"
  STATUS=$(curl -sS -o /tmp/m.json -w '%{http_code}' -X POST -H "$A" -H 'Content-Type: application/json' \
    "$KC/admin/realms/odap/clients/$CLIENT_UUID/protocol-mappers/models" -d "{
      \"name\":\"${MAPPER_NAME}\",
      \"protocol\":\"openid-connect\",
      \"protocolMapper\":\"oidc-usermodel-client-role-mapper\",
      \"config\":{
        \"multivalued\":\"true\",
        \"userinfo.token.claim\":\"false\",
        \"id.token.claim\":\"false\",
        \"access.token.claim\":\"true\",
        \"claim.name\":\"resource_access.\${client_id}.roles\",
        \"jsonType.label\":\"String\",
        \"usermodel.clientRoleMapping.clientId\":\"realm-management\"
      }
    }")
  [ "$STATUS" = "201" ] || fail "mapper POST=$STATUS body=$(cat /tmp/m.json)"
  pass "mapper aangemaakt"
else
  pass "mapper ${MAPPER_NAME} al aanwezig"
fi

# ---------------------------------------------------------------------------
# fullScopeAllowed: existing clients (created before this script learned to
# default to true) may still have it set to false. Idempotently flip.
# ---------------------------------------------------------------------------
CUR_FULL=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients/$CLIENT_UUID" \
  | { grep -oE '"fullScopeAllowed":(true|false)' || true; } | head -1 | cut -d':' -f2)
if [ "$CUR_FULL" = "false" ]; then
  log "fullScopeAllowed=false → patching naar true"
  CLIENT_BODY=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients/$CLIENT_UUID" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); d["fullScopeAllowed"]=True; print(json.dumps(d))')
  STATUS=$(curl -sS -o /dev/null -w '%{http_code}' -X PUT -H "$A" -H 'Content-Type: application/json' \
    "$KC/admin/realms/odap/clients/$CLIENT_UUID" -d "$CLIENT_BODY")
  [ "$STATUS" = "204" ] || fail "client PUT=$STATUS"
  pass "fullScopeAllowed=true"
else
  pass "fullScopeAllowed al true"
fi
