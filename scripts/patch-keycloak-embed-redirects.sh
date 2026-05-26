#!/usr/bin/env bash
# Patch redirect-URIs + web-origins van bestaande Keycloak-clients in een
# *live* odap-realm zodat ze de nieuwe path-routed callbacks accepteren
# (https://platform.odap.local:8443/<service>/...).
#
# De realm.json configmap is de bron voor verse Keycloak-installs;
# voor een lopende cluster moeten we via de admin API patchen want
# Keycloak importeert de realm alleen op first-start.
#
# Idempotent: voegt URIs alleen toe als ze nog niet in de lijst staan.
# Default: poort-forward naar pod (k3d). Geef KC_HOST=... mee voor extern.
#
# Voorbeeld:
#   bash scripts/patch-keycloak-embed-redirects.sh
#   KC_HOST=https://keycloak.example.com \
#     bash scripts/patch-keycloak-embed-redirects.sh

set -euo pipefail

KC_NAMESPACE="${KC_NAMESPACE:-odap-auth}"
KC_ADMIN_USER="${KC_ADMIN_USER:-kcadmin}"
KC_ADMIN_PASS="${KC_ADMIN_PASS:-odap-dev-only-CHANGE-ME}"
KC_HOST="${KC_HOST:-}"
REALM="${REALM:-uwv}"

# Per-client extra redirects + web origins. Telkens: clientId|redirectUri,...|origin,...
PATCHES=(
  "superset|https://platform.odap.local:8443/superset/*,https://platform.example.com/superset/*,https://platform.example.com/superset/*|https://platform.odap.local:8443,https://platform.example.com,https://platform.example.com"
  "airflow|https://platform.odap.local:8443/airflow/*,https://platform.example.com/airflow/*,https://platform.example.com/airflow/*|https://platform.odap.local:8443,https://platform.example.com,https://platform.example.com"
  "jupyter|https://platform.odap.local:8443/jupyter/hub/oauth_callback,https://platform.example.com/jupyter/hub/oauth_callback,https://platform.example.com/jupyter/hub/oauth_callback|https://platform.odap.local:8443,https://platform.example.com,https://platform.example.com"
  "grafana|https://platform.odap.local:8443/grafana/login/generic_oauth,https://platform.example.com/grafana/login/generic_oauth,https://platform.example.com/grafana/login/generic_oauth|https://platform.odap.local:8443,https://platform.example.com,https://platform.example.com"
)

step() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✓\033[0m  %s\n' "$*"; }
warn() { printf '\033[1;33m  !!\033[0m %s\n' "$*"; }

# Bepaal hoe we Keycloak bereiken — port-forward bij ontbreken externe host.
PF_PID=""
cleanup() { [[ -n "$PF_PID" ]] && kill "$PF_PID" 2>/dev/null || true; }
trap cleanup EXIT

if [[ -z "$KC_HOST" ]]; then
  step "port-forward naar keycloak-pod in $KC_NAMESPACE"
  kubectl -n "$KC_NAMESPACE" port-forward svc/keycloak 18080:80 >/dev/null 2>&1 &
  PF_PID=$!
  sleep 2
  KC_HOST="http://localhost:18080"
fi

step "log in als $KC_ADMIN_USER"
TOKEN=$(curl -fsS \
  -d "client_id=admin-cli" \
  -d "username=$KC_ADMIN_USER" \
  -d "password=$KC_ADMIN_PASS" \
  -d "grant_type=password" \
  "${KC_HOST}/realms/master/protocol/openid-connect/token" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
[[ -z "$TOKEN" ]] && { warn "geen token — admin-credentials kloppen niet?"; exit 1; }
ok "ingelogd"

for patch in "${PATCHES[@]}"; do
  IFS='|' read -r CID NEW_REDIRECTS NEW_ORIGINS <<<"$patch"
  step "client=$CID"

  # Lookup client UUID
  CLIENT=$(curl -fsS -H "Authorization: Bearer $TOKEN" \
    "${KC_HOST}/admin/realms/${REALM}/clients?clientId=${CID}" \
    | python3 -c "import sys,json; xs=json.load(sys.stdin); print(json.dumps(xs[0]) if xs else '')")
  [[ -z "$CLIENT" ]] && { warn "client $CID niet gevonden — skip"; continue; }

  UUID=$(echo "$CLIENT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

  # Merge nieuwe redirects + origins in bestaande lijsten, dedupe.
  # Env-vars MOETEN vóór `python3` — anders worden ze als argv doorgegeven
  # en leest os.environ.get(...) niks (en de patch is een no-op).
  UPDATED=$(echo "$CLIENT" | NEW_REDIRECTS="$NEW_REDIRECTS" NEW_ORIGINS="$NEW_ORIGINS" python3 -c "
import sys, json, os
c = json.loads(sys.stdin.read())
new_redirects = [x for x in os.environ.get('NEW_REDIRECTS', '').split(',') if x]
new_origins = [x for x in os.environ.get('NEW_ORIGINS', '').split(',') if x]
existing_redirects = [u for u in (c.get('redirectUris') or []) if u]
existing_origins = [u for u in (c.get('webOrigins') or []) if u]
merged_redirects = list(dict.fromkeys([*existing_redirects, *new_redirects]))
merged_origins = list(dict.fromkeys([*existing_origins, *new_origins]))
c['redirectUris'] = merged_redirects
c['webOrigins'] = merged_origins
print(json.dumps(c))
")

  # PUT update
  HTTP=$(curl -fsS -o /dev/null -w '%{http_code}' \
    -X PUT \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data "$UPDATED" \
    "${KC_HOST}/admin/realms/${REALM}/clients/${UUID}")
  if [[ "$HTTP" == "204" ]]; then
    ok "geüpdatet"
  else
    warn "PUT $CID → HTTP $HTTP"
  fi
done

step "klaar"
