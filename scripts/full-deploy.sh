#!/usr/bin/env bash
# Open Data & Analytics Platform — alles-in-één deploy.
#
# Mode: --mode={k3d|aks}  (default k3d; ook DEPLOYMENT_MODE env)
#
# Stappen voor mode=k3d:
#   1. cluster aanmaken (k3d) — overgeslagen voor aks
#   2. /etc/hosts patchen voor *.${PLATFORM_DOMAIN}
#   3. bootstrap (helm charts + operators) — mode-aware
#   4. platform-ca-bundle ConfigMap
#   5. deploy-platform (manifests, mode-aware kustomize overlays)
#   6. Portal image build + import in cluster
#   7. Live-only Keycloak realm patches
#   8. Bootstrap Airflow/Superset Admin-rol
#   9. Smoke test
#
# Voor mode=aks: zie scripts/azure/aks-bootstrap.sh + aks-deploy.sh; full-deploy
# verwijst daarheen omdat AKS extra cloud-only stappen heeft (DNS upsert,
# public-ingresses, CoreDNS-custom). Run aldaar in plaats van hier.
#
# Idempotent — re-run is veilig, alle stappen skippen bij "already done".
#
# Usage:
#   ./scripts/full-deploy.sh                  # default mode=k3d
#   ./scripts/full-deploy.sh --skip-cluster   # cluster bestaat al
#   ./scripts/full-deploy.sh --skip-bootstrap # helm-installs overslaan

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Mode handling.
# shellcheck source=lib/mode.sh
source "${ROOT}/scripts/lib/mode.sh"
parse_mode_args "$@"

SKIP_CLUSTER=0
SKIP_BOOTSTRAP=0
for arg in "${REMAINING_ARGS[@]}"; do
  case "$arg" in
    --skip-cluster)   SKIP_CLUSTER=1 ;;
    --skip-bootstrap) SKIP_BOOTSTRAP=1 ;;
  esac
done

ok()   { printf '\033[1;32m  ✓\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }

if [[ "${IS_CLOUD}" == "yes" ]]; then
  case "$DEPLOYMENT_MODE" in
    aks)
      fail "mode=aks: gebruik 'make aks-all' (of scripts/azure/aks-bootstrap.sh + aks-deploy.sh).
            full-deploy.sh dekt alleen k3d — AKS heeft extra cloud-only stappen."
      ;;
    stackit)
      fail "mode=stackit: gebruik scripts/stackit/ske-bootstrap.sh + scripts/stackit/ske-deploy.sh.
            full-deploy.sh dekt alleen k3d — StackIT heeft extra cloud-only stappen."
      ;;
  esac
fi

# ---------------------------------------------------------------------- 1
log "1/10  cluster aanmaken (mode=${DEPLOYMENT_MODE})"
if [[ $SKIP_CLUSTER -eq 1 ]]; then
  warn "skip (--skip-cluster)"
else
  make cluster
  ok "k3d cluster up"
fi
require_context

# ---------------------------------------------------------------------- 2
log "2/10  /etc/hosts patchen voor *.${PLATFORM_DOMAIN}"
HOST_SUBDOMAINS=(platform keycloak superset airflow trino minio minio-console \
                 openmetadata grafana prometheus opensearch spark jupyter)
HOSTS_LINE="127.0.0.1"
for sub in "${HOST_SUBDOMAINS[@]}"; do
  HOSTS_LINE="${HOSTS_LINE} ${sub}.${PLATFORM_DOMAIN}"
done
# Spot-check: if the first and last entries are present we assume the line is good.
if grep -q "platform.${PLATFORM_DOMAIN}" /etc/hosts && \
   grep -q "jupyter.${PLATFORM_DOMAIN}" /etc/hosts; then
  ok "alle hostnames al in /etc/hosts"
else
  log "sudo nodig om /etc/hosts te bewerken"
  echo "$HOSTS_LINE" | sudo tee -a /etc/hosts >/dev/null
  ok "hostnames toegevoegd aan /etc/hosts"
fi

# ---------------------------------------------------------------------- 3
log "3/10  bootstrap (Helm charts + Stackable operators) — mode=${DEPLOYMENT_MODE}"
if [[ $SKIP_BOOTSTRAP -eq 1 ]]; then
  warn "skip (--skip-bootstrap)"
else
  bash "$ROOT/scripts/bootstrap.sh" --mode="${DEPLOYMENT_MODE}" \
    || warn "bootstrap meldde fouten — check output; ga door"
  ok "bootstrap done"
fi

# ---------------------------------------------------------------------- 4
log "4/10  platform-ca-bundle ConfigMap (Mozilla public roots + Platform CA)"
# Mozilla public roots zijn essentieel voor cloud-mode: OIDC token-exchange
# tegen keycloak.example.com (LE cert) faalt anders met
# 'unable to get local issuer certificate'. deploy-platform extendt de
# bundle later met de Stackable secret-operator CA voor in-cluster TLS.
kubectl create namespace odap-platform --dry-run=client -o yaml | kubectl apply -f - >/dev/null
TMP=$(mktemp -d)
curl -fsSL --connect-timeout 10 https://curl.se/ca/cacert.pem -o "$TMP/public.crt"
kubectl get secret odap-platform-ca -n cert-manager -o jsonpath='{.data.ca\.crt}' | base64 -d > "$TMP/uwv.crt"
cat "$TMP/public.crt" "$TMP/uwv.crt" > "$TMP/combined.crt"
kubectl -n odap-platform delete configmap platform-ca-bundle --ignore-not-found >/dev/null
kubectl -n odap-platform create configmap platform-ca-bundle \
  --from-file=ca.crt="$TMP/combined.crt" >/dev/null
rm -rf "$TMP"
ok "platform-ca-bundle gemount"

# ---------------------------------------------------------------------- 5
log "5/10  CoreDNS-patch: skip pre-deploy (Service bestaat nog niet)"
warn "post-deploy stap doet de echte patch zodra keycloak-external bestaat"

# ---------------------------------------------------------------------- 6
log "6/10  deploy-platform (alle K8s manifests, mode=${DEPLOYMENT_MODE})"
bash "$ROOT/scripts/deploy-platform.sh" --mode="${DEPLOYMENT_MODE}" \
  || warn "deploy-platform meldde fouten — check output"
ok "platform manifests applied"

# CoreDNS hosts-override voor keycloak.${PLATFORM_DOMAIN} zodat in-cluster
# pods (MinIO/Trino/Superset/Airflow/NiFi/OpenMetadata) Keycloak's externe
# URL kunnen resolveren. De keycloak-external Service in ingress-nginx NS
# (selector-based, robuust tegen pod-restart) is de target.
log "CoreDNS NodeHosts patch (in-cluster keycloak.${PLATFORM_DOMAIN})"
KC_SVC_IP=""
for i in {1..30}; do
  KC_SVC_IP=$(kubectl -n ingress-nginx get svc keycloak-external -o jsonpath='{.spec.clusterIP}' 2>/dev/null || true)
  [[ -n "$KC_SVC_IP" && "$KC_SVC_IP" != "None" ]] && break
  sleep 2
done
if [[ -z "$KC_SVC_IP" || "$KC_SVC_IP" == "None" ]]; then
  warn "keycloak-external Service nog niet beschikbaar; CoreDNS-patch overgeslagen"
else
  kubectl -n kube-system get cm coredns -o yaml > /tmp/coredns.yaml
  KCSVC="$KC_SVC_IP" DOMAIN="$PLATFORM_DOMAIN" python3 <<'EOF'
import os, yaml
d = yaml.safe_load(open('/tmp/coredns.yaml'))
hosts = d.get('data', {}).get('NodeHosts', '') or ''
fqdn = f"keycloak.{os.environ['DOMAIN']}"
lines = [l for l in hosts.splitlines() if fqdn not in l and l.strip()]
lines.append(f"{os.environ['KCSVC']} {fqdn}")
d['data']['NodeHosts'] = '\n'.join(lines) + '\n'
yaml.safe_dump(d, open('/tmp/coredns.yaml', 'w'))
EOF
  kubectl apply -f /tmp/coredns.yaml >/dev/null
  kubectl -n kube-system rollout restart deploy coredns >/dev/null
  kubectl -n kube-system rollout status deploy coredns --timeout=60s >/dev/null || true
  ok "CoreDNS NodeHosts gepatched (keycloak → $KC_SVC_IP)"

  # MinIO doet OIDC discovery alleen bij startup; restart zodat de Console
  # de Keycloak SSO-knop toont.
  if kubectl -n odap-platform get deployment minio >/dev/null 2>&1; then
    kubectl -n odap-platform rollout restart deployment minio >/dev/null
    kubectl -n odap-platform rollout status deployment minio --timeout=120s >/dev/null || true
    ok "MinIO herstart (OIDC discovery picks up de DNS-fix)"
  fi
fi

# ---------------------------------------------------------------------- 7
log "7/10  Portal Docker-image bouwen + in cluster laden (mode=${DEPLOYMENT_MODE})"
docker build -f portal/Dockerfile -t odap/portal:dev . >/dev/null
k3d image import odap/portal:dev -c "${CLUSTER_NAME:-odap-platform}" >/dev/null
# Sidecar voor /api/airflow/* (FastAPI; triggert convert_to_delta DAG).
docker build -f portal/Dockerfile.airflow-bridge \
             -t odap/portal-airflow-bridge:dev . >/dev/null
k3d image import odap/portal-airflow-bridge:dev -c "${CLUSTER_NAME:-odap-platform}" >/dev/null
kubectl -n odap-platform rollout restart deployment portal >/dev/null 2>&1 || true
ok "portal + airflow-bridge images gebouwd + geïmporteerd"

# ---------------------------------------------------------------------- 8
log "8/10  Live-only Keycloak realm patches (TOTP, scopes, mappers, attrs)"
# Wacht tot Keycloak ready
for i in {1..60}; do
  TOKEN=$(kubectl -n odap-auth exec keycloak-0 -c keycloak -- curl -fsS \
    -d "client_id=admin-cli" -d "username=kcadmin" \
    -d "password=odap-dev-only-CHANGE-ME" -d "grant_type=password" \
    http://localhost:8080/realms/master/protocol/openid-connect/token 2>/dev/null \
    | sed 's/.*access_token":"\([^"]*\)".*/\1/' || true)
  [[ -n "$TOKEN" && "$TOKEN" != *"error"* ]] && break
  sleep 3
done

if [[ -z "$TOKEN" ]]; then
  warn "Keycloak niet bereikbaar; sla realm-patches over"
else
  # Export domain/port for the inner bash heredoc.
  export DOMAIN="$PLATFORM_DOMAIN" PORT="$PLATFORM_PORT"
  # bash -c via single-quoted string + escapes — anders interpoleert de
  # outer shell de inner $TOKEN/$ADM en faalt het patch-script silent.
  kubectl -n odap-auth exec keycloak-0 -c keycloak -- bash -c "
DOMAIN='${PLATFORM_DOMAIN}'
PORT='${PLATFORM_PORT}'
T=\$(curl -fsS -d 'client_id=admin-cli' -d 'username=kcadmin' -d 'password=odap-dev-only-CHANGE-ME' -d 'grant_type=password' http://localhost:8080/realms/master/protocol/openid-connect/token | sed 's/.*access_token\":\"\\([^\"]*\\)\".*/\\1/')
KC=http://localhost:8080
A='Authorization: Bearer '\"\$T\"

# 1. TOTP clearen voor demo-admins. NB: PUT moet username + email + enabled
#    MEEsturen — partial body wist andere velden in Keycloak 24+.
for u in platform.admin case.manager data.engineer; do
  KCUID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/users?username=\$u\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
  [ -z \"\$KCUID\" ] && continue
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/users/\$KCUID\" -d \"{\\\"username\\\":\\\"\$u\\\",\\\"email\\\":\\\"\$u@\$DOMAIN\\\",\\\"emailVerified\\\":true,\\\"enabled\\\":true,\\\"requiredActions\\\":[]}\" -o /dev/null
  curl -sS -X DELETE -H \"\$A\" \"\$KC/admin/realms/odap/attack-detection/brute-force/users/\$KCUID\" -o /dev/null
done

# 2. profile + email scopes aanmaken (realm-import skipt deze)
curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" 2>/dev/null | grep -q '\"name\":\"profile\"' || \\
  curl -sS -X POST -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/client-scopes\" -d '{\"name\":\"profile\",\"protocol\":\"openid-connect\",\"attributes\":{\"include.in.token.scope\":\"true\"},\"protocolMappers\":[{\"name\":\"username\",\"protocol\":\"openid-connect\",\"protocolMapper\":\"oidc-usermodel-property-mapper\",\"config\":{\"user.attribute\":\"username\",\"claim.name\":\"preferred_username\",\"jsonType.label\":\"String\",\"id.token.claim\":\"true\",\"access.token.claim\":\"true\",\"userinfo.token.claim\":\"true\"}}]}' -o /dev/null

curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" 2>/dev/null | grep -q '\"name\":\"email\"' || \\
  curl -sS -X POST -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/client-scopes\" -d '{\"name\":\"email\",\"protocol\":\"openid-connect\",\"attributes\":{\"include.in.token.scope\":\"true\"},\"protocolMappers\":[{\"name\":\"email\",\"protocol\":\"openid-connect\",\"protocolMapper\":\"oidc-usermodel-property-mapper\",\"config\":{\"user.attribute\":\"email\",\"claim.name\":\"email\",\"jsonType.label\":\"String\",\"id.token.claim\":\"true\",\"access.token.claim\":\"true\",\"userinfo.token.claim\":\"true\"}}]}' -o /dev/null

# 3. scopes assignen
PROFILE=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" | tr '{' '\\n' | grep '\"name\":\"profile\"' | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
EMAIL=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" | tr '{' '\\n' | grep '\"name\":\"email\"' | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
ROLES=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/client-scopes\" | tr '{' '\\n' | grep '\"name\":\"roles\"' | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
for c in superset airflow openmetadata minio; do
  CID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/clients?clientId=\$c\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
  [ -z \"\$CID\" ] && continue
  for s in \$PROFILE \$EMAIL \$ROLES; do
    curl -sS -X PUT -H \"\$A\" \"\$KC/admin/realms/odap/clients/\$CID/default-client-scopes/\$s\" -o /dev/null
  done
done

# 3b. Lange access-tokens voor de openmetadata client.
# access.token.lifespan=86400 (24h) zodat een werkdag zonder
# re-auth doorgaat. use.refresh.tokens=true is verplicht voor OM 1.12+
# (Pac4j slaat het refresh-token op in z'n session; bij /api/v1/auth/login
# raadpleegt het die en faalt loggedInUser met 401 'No refresh token
# found against session' als refresh-tokens uit staan).
# (Deze attributes staan ook in realm.json voor verse deploys; deze
# patch dekt clusters waar realm-import al was uitgevoerd.)
OM_CID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/clients?clientId=openmetadata\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
if [ -n \"\$OM_CID\" ]; then
  # Stuur ook redirectUris + flow-flags mee: eerdere defensieve PUTs in dit
  # script verstuurden alleen 'attributes' en daardoor reset Keycloak alle
  # andere top-level fields naar default (1 redirectUri, publicClient=true).
  # Resultaat was 'Invalid parameter: redirect_uri' bij login. Idempotent
  # herstellen door volledige client-shape door te geven.
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/clients/\$OM_CID\" -d \"{\\\"publicClient\\\":false,\\\"standardFlowEnabled\\\":true,\\\"implicitFlowEnabled\\\":false,\\\"redirectUris\\\":[\\\"https://openmetadata.\$DOMAIN:\$PORT/*\\\",\\\"https://openmetadata.\$DOMAIN/*\\\",\\\"http://openmetadata.\$DOMAIN:\$PORT/*\\\",\\\"http://openmetadata.\$DOMAIN/*\\\"],\\\"attributes\\\":{\\\"access.token.lifespan\\\":\\\"86400\\\",\\\"client.session.max.lifespan\\\":\\\"86400\\\",\\\"client.session.idle.timeout\\\":\\\"28800\\\",\\\"use.refresh.tokens\\\":\\\"true\\\",\\\"post.logout.redirect.uris\\\":\\\"+\\\"}}\" -o /dev/null
fi

# 4. Unmanaged-attribute-policy enablen — Keycloak 24+ heeft Declarative
#    User Profile met unmanaged-attributes standaard UIT, waardoor de
#    \\\"policy\\\" custom attribute silently genegeerd wordt.
PROFILE_CFG=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/users/profile\" 2>/dev/null)
if ! echo \"\$PROFILE_CFG\" | grep -q '\"unmanagedAttributePolicy\":\"ADMIN_EDIT\"'; then
  echo \"\$PROFILE_CFG\" | sed -e 's/}\$/,\"unmanagedAttributePolicy\":\"ADMIN_EDIT\"}/' > /tmp/up.json
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/users/profile\" --data @/tmp/up.json -o /dev/null
fi

# 5. policy attribute voor MinIO consoleAdmin op demo-admins. NB: PUT
#    moet email + enabled MEEsturen om partial-body wipe te voorkomen.
for u in claims.analyst platform.admin; do
  KCUID=\$(curl -fsS -H \"\$A\" \"\$KC/admin/realms/odap/users?username=\$u\" 2>/dev/null | grep -oE '\"id\":\"[^\"]*\"' | head -1 | cut -d'\"' -f4)
  [ -z \"\$KCUID\" ] && continue
  curl -sS -X PUT -H \"\$A\" -H 'Content-Type: application/json' \"\$KC/admin/realms/odap/users/\$KCUID\" \\
    -d \"{\\\"username\\\":\\\"\$u\\\",\\\"email\\\":\\\"\$u@\$DOMAIN\\\",\\\"emailVerified\\\":true,\\\"enabled\\\":true,\\\"attributes\\\":{\\\"policy\\\":[\\\"consoleAdmin\\\"]}}\" -o /dev/null
done
" 2>&1 | tail -3
  ok "Keycloak runtime patches applied"

  # Path-based redirect-URIs voor /embed/<svc>-flow. Realm-import in
  # configmap dekt verse Keycloak-installs; voor draaiende clusters
  # die het oude realm-JSON al hebben geïmporteerd, doen we hier de
  # PUT via admin API. Idempotent — dedup'pt op bestaande URIs.
  log "Patch Keycloak clients voor /embed/<svc> redirect-URIs"
  bash "${ROOT}/scripts/patch-keycloak-embed-redirects.sh" 2>&1 | tail -5 \
    || warn "embed-redirects-patch faalde — log hierboven"
fi

# ---------------------------------------------------------------------- 9
log "9/10  Bootstrap Admin-rol op demo-users in Airflow + Superset"
# Wacht tot Airflow webserver up
for i in {1..30}; do
  STATE=$(kubectl -n odap-platform get pod -l app.kubernetes.io/name=airflow,app.kubernetes.io/component=webserver \
    -o jsonpath='{.items[0].status.containerStatuses[?(@.name=="airflow")].ready}' 2>/dev/null || true)
  [[ "$STATE" = "true" ]] && break
  sleep 5
done
if [[ "$STATE" = "true" ]]; then
  for u in claims.analyst platform.admin; do
    kubectl -n odap-platform exec airflow-webserver-default-0 -c airflow -- \
      airflow users add-role -e "$u@${PLATFORM_DOMAIN}" -r Admin 2>/dev/null | tail -1 | grep -v "does not exist" || true
  done
  ok "Airflow Admin-rol toegekend aan demo-users (na hun eerste login)"
else
  warn "Airflow webserver nog niet up; rol-toekenning na eerste login handmatig"
fi

# Superset idem
SUP=$(kubectl -n odap-platform get pod superset-node-default-0 -o jsonpath='{.status.containerStatuses[?(@.name=="superset")].ready}' 2>/dev/null || true)
if [[ "$SUP" = "true" ]]; then
  kubectl -n odap-platform exec superset-node-default-0 -c superset -- python3 <<'PYEOF' 2>/dev/null | tail -3 || true
from superset.app import create_app
app = create_app()
with app.app_context():
    from flask_appbuilder.security.sqla.models import User, Role
    from superset import db
    admin = db.session.query(Role).filter_by(name='Admin').first()
    for u in db.session.query(User).all():
        if not u.roles or all(r.name == 'Public' for r in u.roles):
            u.roles = [admin]
            db.session.commit()
            print(f'upgraded {u.username} -> Admin')
PYEOF
  ok "Superset Admin-rol toegekend aan demo-users"
fi

# ---------------------------------------------------------------------- 10
log "10/11 smoke tests (portal + embed-shell)"
bash tests/smoke/09-portal-up.sh   || warn "smoke 09 meldt fouten"
bash tests/smoke/14-embed-shell.sh || warn "smoke 14 meldt fouten"

# ---------------------------------------------------------------------- 11
log "11/11 OpenMetadata demo-seed: UI-fix + UC-mart entities + CGM-glossary links"
# Drie idempotente acties die OM representatief maken voor de demo:
#  - om-fix-search-mapping: patcht OS-index mappings — OM 1.12 markeert
#                           glossaryTags/classificationTags als plain text
#                           waardoor de Explore-UI 500't bij elke search.
#                           Geen rebuild nodig; fielddata=true online.
#  - om-demo-seed         : synthetiseert UC-mart tabel-entities + governance-
#                           meta (owner/domain/dataProduct/Tier/CGM/PII) voor
#                           UCs die dbt nog niet in Trino heeft gematerialiseerd.
#  - om-glossary-link     : koppelt CGM-termen (Klantreis, EventStream, Fase,
#                           Persona, Werknemer, Werkgever, Dienstverband, etc.)
#                           aan bronze stg_- en mart-tables die de standaard
#                           enrichment niet dekt.
# Demo-seed + glossary-link wachten zelf op de openmetadata-init Job
# (teams/domains/dataProducts/glossary). Faalt onschadelijk als OM nog
# opspint — re-run met 'make om-fix-search-mapping && make om-demo-seed
# && make om-glossary-link' is altijd veilig.
bash "$ROOT/scripts/om-fix-search-mapping.sh" || warn "om-fix-search-mapping meldt fouten — UI Explore kan leeg blijven"
bash "$ROOT/scripts/om-demo-seed.sh"          || warn "om-demo-seed meldt fouten — re-run handmatig"
bash "$ROOT/scripts/om-glossary-link.sh"      || warn "om-glossary-link meldt fouten — re-run handmatig"

echo
ok "Alles klaar. Open: https://platform.${PLATFORM_DOMAIN}:${PLATFORM_PORT}/"
echo "Login: claims.analyst / odap-dev-only-CHANGE-ME-Wia2026"
echo "Of:    platform.admin   / odap-dev-only-CHANGE-ME-Admin2026"
