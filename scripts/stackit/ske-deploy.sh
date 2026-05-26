#!/usr/bin/env bash
# Deploy platform manifests on the StackIT SKE cluster.
# Thin wrapper around scripts/deploy-platform.sh --mode=stackit with stackit-
# specific post-steps:
#   - Public DNS apex+wildcard upsert in Azure DNS (example.com zone
#     lives in dev-stackable-rg).
#   - Public ingress manifests (infrastructure/stackit/public-ingresses.yaml)
#     once Phase 4 has produced them.
#
# Compared to scripts/azure/aks-deploy.sh, this script does NOT do:
#   - CoreDNS hosts-override (AKS-specific quirk to route
#     keycloak.odap.local in-cluster — not needed since SKE doesn't
#     inherit the .local legacy and we use the public domain end-to-end).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export DEPLOYMENT_MODE=stackit
# shellcheck source=../lib/mode.sh
source "$ROOT/scripts/lib/mode.sh"
parse_mode_args
require_context

bash "$ROOT/scripts/deploy-platform.sh" --mode=stackit

# ---- Ensure public DNS apex+wildcard exist in Azure DNS ----
# Idempotent — `az network dns record-set a add-record` is upsert-like
# (it adds if missing). Skipped if `az` cli or the DNS zone resource group
# isn't available (e.g. running from a machine without Azure auth).
DNS_RG="${PUBLIC_DNS_RG:-dev-stackable-rg}"
DNS_ZONE="${PUBLIC_DNS_ZONE:-example.com}"
FLOATING_IP="${STACKIT_FLOATING_IP:-188.34.84.39}"

if command -v az >/dev/null 2>&1 && az network dns zone show -g "$DNS_RG" -n "$DNS_ZONE" >/dev/null 2>&1; then
  log "stackit-post: ensure apex + wildcard A records → $FLOATING_IP in $DNS_RG/$DNS_ZONE"
  for name in "@" "*"; do
    az network dns record-set a add-record \
      -g "$DNS_RG" -z "$DNS_ZONE" \
      --record-set-name "$name" \
      --ipv4-address "$FLOATING_IP" \
      --ttl 300 \
      --output none 2>/dev/null || true
  done
else
  warn "skip Azure DNS upsert (az missing or $DNS_RG/$DNS_ZONE not accessible)"
fi

# ---- Let's Encrypt ClusterIssuer (HTTP-01) ----
# Must exist before the per-service Certificates (in public-ingresses.yaml)
# can be issued by cert-manager. Idempotent apply.
if [[ -f "$ROOT/infrastructure/stackit/cluster-issuer.yaml" ]]; then
  log "stackit-post: applying letsencrypt ClusterIssuers (HTTP-01)"
  # cert-manager CRDs are installed by bootstrap.sh; wait briefly in case
  # we're racing a fresh bootstrap.
  kubectl wait --for=condition=Established crd/clusterissuers.cert-manager.io --timeout=2m >/dev/null
  kubectl apply -f "$ROOT/infrastructure/stackit/cluster-issuer.yaml" >/dev/null
fi

# ---- Public-domain ingresses ----
# 10 Certificate+Ingress pairs (keycloak, grafana, prometheus, minio,
# minio-api, superset, airflow, dbt-docs, openmetadata, opensearch).
# Idempotent apply — missing file is non-fatal (in-cluster Services still
# reachable via the chart-managed *.odap.local ingresses).
if [[ -f "$ROOT/infrastructure/stackit/public-ingresses.yaml" ]]; then
  log "stackit-post: applying public-ingresses.yaml"
  kubectl apply -f "$ROOT/infrastructure/stackit/public-ingresses.yaml" >/dev/null
else
  warn "infrastructure/stackit/public-ingresses.yaml not found — services will only be reachable in-cluster."
fi

# ---- Keycloak redirect-URI patches ----
# Base realm.json only registers *.odap.local URIs. On stackit
# every OIDC client must additionally accept the example.com callbacks
# or Keycloak rejects with "Invalid parameter: redirect_uri". Idempotent —
# the patch_uris function unions new URIs onto the existing list.
log "stackit-post: adding example.com redirect URIs to OIDC clients"
KCPOD=$(kubectl -n odap-auth get pods -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -z "$KCPOD" ]]; then
  warn "Keycloak pod not found; skipping redirect-URI patches"
else
  # Wait for Keycloak admin endpoint to respond — newly-deployed pod takes a
  # moment to finish realm import.
  TOKEN=""
  for _ in $(seq 1 30); do
    TOKEN=$(kubectl -n odap-auth exec "$KCPOD" -c keycloak -- curl -fsS \
      -d "client_id=admin-cli" -d "username=kcadmin" \
      -d "password=odap-dev-only-CHANGE-ME" -d "grant_type=password" \
      http://localhost:8080/realms/master/protocol/openid-connect/token 2>/dev/null \
      | sed 's/.*access_token":"\([^"]*\)".*/\1/' || true)
    [[ -n "$TOKEN" && "$TOKEN" != *"error"* ]] && break
    sleep 3
  done

  if [[ -z "$TOKEN" ]]; then
    warn "Keycloak admin token not obtained; skipping redirect-URI patches"
  else
    kubectl -n odap-auth exec "$KCPOD" -c keycloak -- bash -c '
T=$(curl -fsS -d "client_id=admin-cli" -d "username=kcadmin" -d "password=odap-dev-only-CHANGE-ME" -d "grant_type=password" http://localhost:8080/realms/master/protocol/openid-connect/token | sed "s/.*access_token\":\"\([^\"]*\)\".*/\1/")
A="Authorization: Bearer $T"
KC=http://localhost:8080

patch_uris() {
  local c=$1; shift
  local CID=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients?clientId=$c" 2>/dev/null | grep -oE "\"id\":\"[^\"]*\"" | head -1 | cut -d\" -f4)
  [ -z "$CID" ] && return
  local CUR=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients/$CID" | grep -oE "\"redirectUris\":\[[^]]*\]" | head -1 | sed -E "s/.*\[(.*)\]/\1/")
  declare -A SEEN
  local OUT=()
  IFS=, read -ra ITEMS <<< "$CUR"
  for u in "${ITEMS[@]}"; do u=$(echo "$u" | tr -d \"); [ -n "$u" ] && SEEN[$u]=1 && OUT+=("\"$u\""); done
  for u in "$@"; do [ -z "${SEEN[$u]:-}" ] && OUT+=("\"$u\"") && SEEN[$u]=1; done
  local NEW="[$(IFS=,; echo "${OUT[*]}")]"
  curl -sS -X PUT -H "$A" -H "Content-Type: application/json" "$KC/admin/realms/odap/clients/$CID" -d "{\"redirectUris\":$NEW}" -o /dev/null
}

patch_uris portal       "https://platform.example.com/oauth2/callback" "https://example.com/oauth2/callback" "https://www.example.com/oauth2/callback"
patch_uris superset     "https://superset.example.com/*"
patch_uris airflow      "https://airflow.example.com/*" "https://airflow.example.com/oauth-authorized/keycloak"
patch_uris openmetadata "https://openmetadata.example.com/*" "https://openmetadata.example.com/callback"
patch_uris minio        "https://minio.example.com/oauth_callback" "https://minio.example.com/*"
patch_uris jupyter      "https://jupyter.example.com/hub/oauth_callback"
' >/dev/null 2>&1 || warn "redirect-URI patch failed — fix manually in Keycloak admin (browse to platform.example.com/realms/odap/clients)"
    log "  6 OIDC clients patched (portal, superset, airflow, openmetadata, minio, jupyter)"
  fi
fi

log "StackIT deploy klaar."
