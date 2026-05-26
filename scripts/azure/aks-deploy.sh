#!/usr/bin/env bash
# Deploy platform manifests on the AKS cluster.
# Thin wrapper around scripts/deploy-platform.sh --mode=aks with AKS-specific
# post-steps:
#  - CoreDNS hosts-override (`coredns-custom` ConfigMap) zodat
#    keycloak.odap.local in-cluster routeert naar de keycloak-external
#    Service in ingress-nginx (zie platform/02-authentication/keycloak-external-svc.yaml).
#  - Public DNS upsert (CNAME → apex) for every *.${PLATFORM_DOMAIN} subdomain.
#  - MinIO restart zodat de OIDC-discovery slaagt na de DNS-fix (Console toont
#    anders geen Keycloak SSO knop).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Force mode=aks regardless of caller args.
export DEPLOYMENT_MODE=aks
# shellcheck source=../lib/mode.sh
source "$ROOT/scripts/lib/mode.sh"
parse_mode_args
require_context

bash "$ROOT/scripts/deploy-platform.sh" --mode=aks

# ---- AKS-only: sweep chart-style portal leftovers ----
# platform-overlays/aks/15-portal/ uses kustomize `$patch: delete` to
# remove the chart-style `portal` Deployment/Service/Ingress from the
# rendered output — but `kubectl apply -k` only creates/updates, never
# deletes resources missing from the manifest. If a prior deploy left
# the chart-style portal in place (e.g. the cluster was first deployed
# on an older revision without the overlay), explicitly remove it here.
# Idempotent (`--ignore-not-found`).
log "AKS-post: remove chart-style portal leftovers (platform-landing owns the public portal on AKS)"
kubectl -n odap-platform delete deployment portal --ignore-not-found
kubectl -n odap-platform delete service portal --ignore-not-found
kubectl -n odap-platform delete ingress portal --ignore-not-found

# ---- AKS-only: mirror postgres-postgresql secret naar odap-meta ----
# De openmetadata-jwt-rotate + openmetadata-to-opa-sync CronJobs draaien in
# odap-meta en hebben de Postgres-creds nodig om de bot-JWT uit user_entity
# te lezen / patchen. scripts/bootstrap.sh:537 spiegelt dit secret naar
# odap-meta na de Postgres helm-install, maar op een fresh AKS-bootstrap
# valt die spiegeling soms uit (Postgres-secret bestaat dan nog niet in
# odap-data) → odap-meta blijft secret-loos en alle JWT-jobs schieten in
# CreateContainerConfigError. Hier zelf-helend: idempotent re-mirror op
# elke deploy.
log "AKS-post: mirror postgres-postgresql secret naar odap-meta (voor JWT-rotate + OPA-sync CronJobs)"
PG_PW=$(kubectl -n odap-data get secret postgres-postgresql -o jsonpath='{.data.password}' 2>/dev/null | base64 -d || true)
if [[ -z "${PG_PW:-}" ]]; then
  # Bitnami chart pre-12.x exposeert de root-password onder `postgres-password`.
  PG_PW=$(kubectl -n odap-data get secret postgres-postgresql -o jsonpath='{.data.postgres-password}' 2>/dev/null | base64 -d || true)
fi
if [[ -n "${PG_PW:-}" ]]; then
  kubectl -n odap-meta create secret generic postgres-postgresql \
    --from-literal=password="${PG_PW}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
else
  warn "  postgres-postgresql secret niet gevonden in odap-data — JWT-rotate + OPA-sync zullen falen"
fi

# ---- AKS-only: ensure public-domain DNS records exist ----
# Every *.example.com subdomain needs a CNAME → apex (which
# is an A record at the ingress static IP, set up by terraform/aks-up).
# Idempotent — `az network dns record-set cname set-record` is upsert.
# Skipped if `az` cli or the DNS zone resource group isn't available
# (e.g. running outside the platform Azure tenant).
DNS_RG="${PUBLIC_DNS_RG:-ai-trial-rg}"
DNS_ZONE="${PUBLIC_DNS_ZONE:-example.com}"
if command -v az >/dev/null 2>&1 && az network dns zone show -g "$DNS_RG" -n "$DNS_ZONE" >/dev/null 2>&1; then
  log "AKS-post: ensure CNAMEs for all public subdomains in $DNS_RG/$DNS_ZONE"
  for sub in platform www keycloak airflow grafana prometheus minio minio-api \
             superset dbt-docs openmetadata opensearch nifi trino \
             spark jupyter multica; do
    az network dns record-set cname set-record \
      -g "$DNS_RG" -z "$DNS_ZONE" \
      --record-set-name "$sub" \
      --cname "$DNS_ZONE" \
      --ttl 3600 \
      --output none 2>/dev/null || warn "  could not upsert CNAME $sub.$DNS_ZONE"
  done
else
  warn "skip DNS CNAME upsert (az missing or $DNS_RG/$DNS_ZONE not accessible)"
fi

# ---- AKS-only: public-domain ingresses ----
# Adds Cert + Ingress pairs for every *.example.com
# subdomain (platform, keycloak, airflow, grafana, prometheus, minio,
# minio-api, superset, dbt-docs, openmetadata, opensearch, nifi, trino).
# cert-manager solves DNS-01 via the azuredns ClusterIssuer.
if [[ -f "$ROOT/infrastructure/azure/public-ingresses.yaml" ]]; then
  log "AKS-post: applying public-ingresses.yaml"
  kubectl apply -f "$ROOT/infrastructure/azure/public-ingresses.yaml" >/dev/null
fi

# ---- AKS-only post-deploy: CoreDNS hosts-override ----
# AKS CoreDNS gebruikt een 'coredns-custom' ConfigMap met *.override files
# die geïmporteerd worden via `import custom/*.override` in de hoofd-Corefile.
# We pinnen `keycloak.odap.local` op de ClusterIP van de
# keycloak-external Service (zie platform/02-authentication/keycloak-external-svc.yaml).
log "AKS-post: CoreDNS hosts-override voor keycloak.odap.local"
KCEXT_IP=""
for i in $(seq 1 30); do
  KCEXT_IP=$(kubectl -n ingress-nginx get svc keycloak-external -o jsonpath='{.spec.clusterIP}' 2>/dev/null || true)
  [[ -n "$KCEXT_IP" && "$KCEXT_IP" != "None" ]] && break
  sleep 2
done
if [[ -z "$KCEXT_IP" || "$KCEXT_IP" == "None" ]]; then
  warn "keycloak-external Service nog niet beschikbaar; sla CoreDNS-patch over"
else
  log "  keycloak-external ClusterIP: $KCEXT_IP"
  kubectl -n kube-system create configmap coredns-custom \
    --from-literal=keycloak.override="hosts {
    $KCEXT_IP keycloak.odap.local
    fallthrough
}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  kubectl -n kube-system rollout restart deploy coredns >/dev/null
  kubectl -n kube-system rollout status deploy coredns --timeout=60s >/dev/null || warn "CoreDNS rollout traag"
  log "  CoreDNS gepatched + herstart"
fi

# ---- Keycloak runtime patches (profile + email scopes, policy attribute) ----
# realm.json import skipt deze omdat het IGNORE_EXISTING strategy gebruikt
# en alleen scopes aanmaakt die expliciet in de JSON staan. Zonder deze patch
# faalt SSO met `invalid_scope: Invalid scopes: openid profile email roles`.
log "AKS-post: Keycloak realm patches (profile + email scopes, attach to clients)"
KCPOD=$(kubectl -n odap-auth get pods -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -z "$KCPOD" ]]; then
  warn "Keycloak pod niet gevonden; sla realm-patches over"
else
  # Wacht tot Keycloak bereikbaar is
  TOKEN=""
  for i in $(seq 1 30); do
    TOKEN=$(kubectl -n odap-auth exec "$KCPOD" -c keycloak -- curl -fsS \
      -d "client_id=admin-cli" -d "username=kcadmin" \
      -d "password=odap-dev-only-CHANGE-ME" -d "grant_type=password" \
      http://localhost:8080/realms/master/protocol/openid-connect/token 2>/dev/null \
      | sed 's/.*access_token":"\([^"]*\)".*/\1/' || true)
    [[ -n "$TOKEN" && "$TOKEN" != *"error"* ]] && break
    sleep 3
  done

  if [[ -z "$TOKEN" ]]; then
    warn "Keycloak admin-token niet verkregen; sla realm-patches over"
  else
    kubectl -n odap-auth exec "$KCPOD" -c keycloak -- bash -c "
T=\$(curl -fsS -d 'client_id=admin-cli' -d 'username=kcadmin' -d 'password=odap-dev-only-CHANGE-ME' -d 'grant_type=password' http://localhost:8080/realms/master/protocol/openid-connect/token | sed 's/.*access_token\":\"\\([^\"]*\\)\".*/\\1/')
KC=http://localhost:8080
A='Authorization: Bearer '\"\$T\"

# 1. profile + email scopes aanmaken (idempotent; realm-import skipt deze)
curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" 2>/dev/null | grep -q '\"name\":\"profile\"' || \\
  curl -sS -X POST -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/client-scopes\" -d '{\"name\":\"profile\",\"protocol\":\"openid-connect\",\"attributes\":{\"include.in.token.scope\":\"true\"},\"protocolMappers\":[{\"name\":\"username\",\"protocol\":\"openid-connect\",\"protocolMapper\":\"oidc-usermodel-property-mapper\",\"config\":{\"user.attribute\":\"username\",\"claim.name\":\"preferred_username\",\"jsonType.label\":\"String\",\"id.token.claim\":\"true\",\"access.token.claim\":\"true\",\"userinfo.token.claim\":\"true\"}}]}' -o /dev/null

curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" 2>/dev/null | grep -q '\"name\":\"email\"' || \\
  curl -sS -X POST -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/client-scopes\" -d '{\"name\":\"email\",\"protocol\":\"openid-connect\",\"attributes\":{\"include.in.token.scope\":\"true\"},\"protocolMappers\":[{\"name\":\"email\",\"protocol\":\"openid-connect\",\"protocolMapper\":\"oidc-usermodel-property-mapper\",\"config\":{\"user.attribute\":\"email\",\"claim.name\":\"email\",\"jsonType.label\":\"String\",\"id.token.claim\":\"true\",\"access.token.claim\":\"true\",\"userinfo.token.claim\":\"true\"}}]}' -o /dev/null

# 2. scopes assignen aan alle OIDC-clients (idempotent — PUT geeft 204 ook bij re-assign)
PROFILE=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" | tr '{' '\\n' | grep '\"name\":\"profile\"' | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
EMAIL=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" | tr '{' '\\n' | grep '\"name\":\"email\"' | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
ROLES=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" | tr '{' '\\n' | grep '\"name\":\"roles\"' | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
for c in superset airflow nifi openmetadata minio; do
  CID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/clients?clientId=\$c\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
  [ -z \"\$CID\" ] && continue
  for s in \$PROFILE \$EMAIL \$ROLES; do
    curl -sS -X PUT -H \"\$A\" \"\$KC/admin/realms/odap/clients/\$CID/default-client-scopes/\$s\" -o /dev/null
  done
done

# 2b. Lange access-tokens voor de openmetadata client.
# access.token.lifespan=86400 (24h) zodat een werkdag zonder re-auth
# doorgaat. use.refresh.tokens=true is verplicht voor OM 1.12+
# (Pac4j slaat het refresh-token op in z'n session; bij /api/v1/auth/login
# raadpleegt het die en faalt loggedInUser met 401 'No refresh token
# found against session' als refresh-tokens uit staan).
OM_CID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/clients?clientId=openmetadata\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
if [ -n \"\$OM_CID\" ]; then
  # Idempotent: stuur volledige client-shape — alleen 'attributes' meegeven
  # reset andere fields (redirectUris, publicClient, flows) naar defaults.
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/clients/\$OM_CID\" -d '{\"publicClient\":false,\"standardFlowEnabled\":true,\"implicitFlowEnabled\":false,\"redirectUris\":[\"https://openmetadata.odap.local:8443/*\",\"https://openmetadata.odap.local/*\",\"http://openmetadata.odap.local:8443/*\",\"http://openmetadata.odap.local/*\"],\"attributes\":{\"access.token.lifespan\":\"86400\",\"client.session.max.lifespan\":\"86400\",\"client.session.idle.timeout\":\"28800\",\"use.refresh.tokens\":\"true\",\"post.logout.redirect.uris\":\"+\"}}' -o /dev/null
fi

# 3. Unmanaged attribute policy enablen — Keycloak 24+ heeft Declarative
#    User Profile met unmanaged-attributes standaard UIT. Zonder deze
#    setting wordt de \\\"policy\\\" custom attribute silently genegeerd
#    (PUT geeft 204 maar er wordt niets opgeslagen).
PROFILE_CFG=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/users/profile\" 2>/dev/null)
if ! echo \"\$PROFILE_CFG\" | grep -q '\"unmanagedAttributePolicy\":\"ADMIN_EDIT\"'; then
  echo \"\$PROFILE_CFG\" | sed -e 's/}\$/,\"unmanagedAttributePolicy\":\"ADMIN_EDIT\"}/' > /tmp/up.json
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/users/profile\" --data @/tmp/up.json -o /dev/null
fi

# 4. policy attribute voor MinIO consoleAdmin op demo-admins. NB: PUT
#    moet email + enabled MEEsturen — partial body wist andere velden.
for u in claims.analyst platform.admin; do
  KCUID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/users?username=\$u\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
  [ -z \"\$KCUID\" ] && continue
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/users/\$KCUID\" \\
    -d \"{\\\"username\\\":\\\"\$u\\\",\\\"email\\\":\\\"\$u@odap.local\\\",\\\"emailVerified\\\":true,\\\"enabled\\\":true,\\\"attributes\\\":{\\\"policy\\\":[\\\"consoleAdmin\\\"]}}\" -o /dev/null
done

# 5. TOTP-requirement clearen voor demo-admins zodat eerste login simpel is
for u in platform.admin case.manager data.engineer; do
  KCUID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/users?username=\$u\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
  [ -z \"\$KCUID\" ] && continue
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/users/\$KCUID\" -d \"{\\\"username\\\":\\\"\$u\\\",\\\"email\\\":\\\"\$u@odap.local\\\",\\\"emailVerified\\\":true,\\\"enabled\\\":true,\\\"requiredActions\\\":[]}\" -o /dev/null
  curl -sS -X DELETE -H \"\$A\" \"\$KC/admin/realms/odap/attack-detection/brute-force/users/\$KCUID\" -o /dev/null
done
" >/dev/null 2>&1
    log "  Keycloak realm-patches toegepast"

    # ---- Add .cloud redirect URIs to OIDC clients ----
    # The base realm.json registers only *.odap.local/* as valid
    # redirect URIs. On AKS, ingress-nginx rewrites Location: .local Keycloak
    # -> .cloud Keycloak (via proxy-redirect-from/-to in the cloud-ingresses
    # manifest), so the browser ends up at .cloud — but Keycloak then rejects
    # the .cloud redirect_uri parameter unless it's in the allowed list. Add
    # the .cloud variants here, idempotent (skip if already present).
    log "AKS-post: add .cloud redirect URIs to OIDC clients"
    kubectl -n odap-auth exec "$KCPOD" -c keycloak -- bash -c "
T=\$(curl -fsS -d 'client_id=admin-cli' -d 'username=kcadmin' -d 'password=odap-dev-only-CHANGE-ME' -d 'grant_type=password' http://localhost:8080/realms/master/protocol/openid-connect/token | sed 's/.*access_token\":\"\\([^\"]*\\)\".*/\\1/')
A=\"Authorization: Bearer \$T\"
KC=http://localhost:8080

patch_uris() {
  local c=\$1; shift
  local CID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/clients?clientId=\$c\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
  [ -z \"\$CID\" ] && return
  local CUR=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/clients/\$CID\" | grep -oE '\"redirectUris\":\\[[^]]*\\]' | head -1 | sed -E 's/.*\\[(.*)\\]/\\1/')
  declare -A SEEN
  local OUT=()
  IFS=, read -ra ITEMS <<< \"\$CUR\"
  for u in \"\${ITEMS[@]}\"; do u=\$(echo \"\$u\" | tr -d '\"'); SEEN[\$u]=1; OUT+=(\"\\\"\$u\\\"\"); done
  for u in \"\$@\"; do [ -z \"\${SEEN[\$u]:-}\" ] && OUT+=(\"\\\"\$u\\\"\") && SEEN[\$u]=1; done
  local NEW=\"[\$(IFS=,; echo \"\${OUT[*]}\")]\"
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/clients/\$CID\" -d \"{\\\"redirectUris\\\":\$NEW}\" -o /dev/null
}

patch_uris superset 'https://superset.odap-platform.cloud/*' 'https://superset.odap-platform.cloud:8443/*'
patch_uris airflow 'https://airflow.odap-platform.cloud/*' 'https://airflow.odap-platform.cloud:8443/*'
patch_uris openmetadata 'https://openmetadata.odap-platform.cloud/*' 'https://openmetadata.odap-platform.cloud:8443/*'
patch_uris minio 'https://minio-console.odap-platform.cloud:8443/oauth_callback' 'https://minio-console.odap-platform.cloud:8443/*'
patch_uris portal 'https://platform.odap-platform.cloud:8443/oauth2/callback' 'https://platform.odap-platform.cloud/oauth2/callback'
patch_uris jupyter 'https://jupyter.odap-platform.cloud/hub/oauth_callback' 'https://jupyter.odap-platform.cloud:8443/hub/oauth_callback'

# Also register the example.com redirects (current public
# DNS — the .cloud variants above are kept for backward compat).
# NB: nifi en trino zijn niet langer publiek bereikbaar (geen Ingress
# meer); flows worden as-code beheerd en Trino-queries gaan via
# Superset/Jupyter/dbt/Airflow. Geen redirect URIs nodig.
patch_uris superset 'https://superset.example.com/*'
patch_uris airflow 'https://airflow.example.com/*' 'https://airflow.example.com/oauth-authorized/keycloak'
patch_uris openmetadata 'https://openmetadata.example.com/*' 'https://openmetadata.example.com/callback'
patch_uris minio 'https://minio.example.com/oauth_callback' 'https://minio.example.com/*'
patch_uris portal 'https://platform.example.com/oauth2/callback' 'https://example.com/oauth2/callback'
patch_uris jupyter 'https://jupyter.example.com/hub/oauth_callback'
" >/dev/null 2>&1 || warn "  redirect-URI patch failed (browse Keycloak admin to fix manually)"
    log "  .cloud + .example.com redirect URIs added (idempotent)"
  fi
fi

# ---- MinIO restart zodat OIDC-discovery slaagt ----
# MinIO doet OIDC discovery alleen bij startup. Als de pod al bestond vóór
# de DNS-fix klaar was, faalt OIDC en is er geen Keycloak-knop in Console.
if kubectl -n odap-platform get deployment minio >/dev/null 2>&1; then
  log "AKS-post: MinIO herstart (OIDC discovery na DNS-fix)"
  kubectl -n odap-platform rollout restart deployment minio >/dev/null
  kubectl -n odap-platform rollout status deployment minio --timeout=120s >/dev/null \
    || warn "MinIO rollout traag"
fi

log "AKS deploy klaar."
