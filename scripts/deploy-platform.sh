#!/usr/bin/env bash
# Deploy alle platform-manifests onder platform/ (fasen 2-9).
#
# Mode-aware: per component wordt platform/<comp>/overlays/<mode>/ gebruikt
# als die bestaat, anders platform/<comp>/ (legacy flat layout).
# Local-only post-steps (CoreDNS hosts-rewrite voor *.${PLATFORM_DOMAIN})
# draaien alleen op k3d. Op AKS doet scripts/azure/aks-deploy.sh die.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Mode handling.
# shellcheck source=lib/mode.sh
source "${ROOT}/scripts/lib/mode.sh"
parse_mode_args "$@"
require_context

# Trino catalog templates renderen voor we 09-trino aanraken.
log "Rendering Trino catalogs (TABLE_FORMAT=${TABLE_FORMAT:-from-config})"
python3 "$ROOT/scripts/render-trino-catalogs.py"

# Spark-jobs sync — kustomize kan niet uit ../../<dir> laden zonder
# load-restrictor=None, dus we kopieren naar platform/08-spark/scripts/.
log "Syncing spark-jobs/ -> platform/08-spark/scripts/"
mkdir -p "$ROOT/platform/08-spark/scripts"
cp "$ROOT/spark-jobs/streaming_files_to_lakehouse.py" "$ROOT/platform/08-spark/scripts/"
cp "$ROOT/spark-jobs/lib/lakehouse_io.py"             "$ROOT/platform/08-spark/scripts/"
# WIA bronze→silver→gold demo (parallel-Spark-pad naast dbt).
cp "$ROOT/spark-jobs/seed_bronze_wia.py"              "$ROOT/platform/08-spark/scripts/"
cp "$ROOT/spark-jobs/batch_silver_wia.py"             "$ROOT/platform/08-spark/scripts/"
cp "$ROOT/spark-jobs/batch_gold_wia.py"               "$ROOT/platform/08-spark/scripts/"

# Bootstrap dev-placeholder secrets for layers that need them. Same pattern
# as the om-bridge target in the Makefile: only generate if missing, so a
# re-run never clobbers real values. Skipping these would crash 17-multica
# on first apply (Postgres + backend deployments reference the secrets).
log "Multica: ensure dev-placeholder secrets exist (idempotent)"
kubectl create namespace odap-platform --dry-run=client -o yaml | kubectl apply -f - >/dev/null
if ! kubectl -n odap-platform get secret multica-postgres >/dev/null 2>&1; then
  PG_PW=$(openssl rand -hex 24)
  kubectl -n odap-platform create secret generic multica-postgres \
    --from-literal=POSTGRES_PASSWORD="$PG_PW"
  kubectl -n odap-platform create secret generic multica-backend \
    --from-literal=JWT_SECRET="$(openssl rand -hex 32)" \
    --from-literal=DATABASE_URL="postgres://multica:${PG_PW}@multica-postgres:5432/multica?sslmode=disable"
  ok "multica-postgres + multica-backend secrets seeded (dev values)"
else
  log "multica secrets already present — skipping seed"
fi

# Out-of-band secrets for 19-nanitics-observatory and 20-multica-daemon.
# These CANNOT be auto-seeded (Foundry key is the operator's Azure asset;
# Multica PAT must be minted in the UI). Warn loudly if missing so the
# operator knows the watcher / daemon pods will crash-loop until they
# are provisioned — but don't fail the deploy, since the rest of the
# platform comes up independently and the pods recover on their own
# once the Secrets land.
check_optional_secret() {
  local name="$1" component="$2" hint="$3"
  if ! kubectl -n odap-platform get secret "$name" >/dev/null 2>&1; then
    warn "${component}: Secret '${name}' not found — pod will crash-loop until provisioned. ${hint}"
  fi
}
check_optional_secret "nanitics-azure-foundry" "19-nanitics-observatory" \
  "See platform/19-nanitics-observatory/secret.yaml for the kubectl create command."
check_optional_secret "multica-daemon-auth" "20-multica-daemon" \
  "Mint a PAT in Multica UI (Settings → API Tokens), then platform/20-multica-daemon/secret-token.yaml has the kubectl recipe."

# Volgorde van applicatie. Per directory een README.md (TODO fase 2+).
LAYERS=(
  "platform/00-namespaces"
  "platform/01-secrets"
  "platform/02-authentication"
  "platform/03-storage"
  # 04-zookeeper, 06-kafka, 07-nifi disabled — UC11 leest uit s3a://odap-raw/
  "platform/05-hive-metastore"
  "platform/08-spark"
  "platform/09-trino"
  "platform/10-opa"
  "platform/11-airflow"
  "platform/12-superset"
  "platform/13-openmetadata-config"
  "platform/14-monitoring"
  "platform/15-portal"
  "platform/16-jupyter"
  "platform/17-multica"
  "platform/19-nanitics-observatory"
  "platform/20-multica-daemon"
)
# NB: 18-om-access-bridge is NOT in this LAYERS array — it needs the OM
# JWT seeded into its Secret before deploy, plus a Keycloak-client +
# OM-subscription setup pass. We call `make deploy-om-bridge` at the
# end of this script (after openmetadata-admin secret exists). Set
# SKIP_OM_BRIDGE=1 to opt out.
#
# 19-nanitics-observatory and 20-multica-daemon land here despite needing
# out-of-band secrets, because the secrets can't be auto-seeded (operator
# decisions) and the pods give clear error messages while waiting. The
# check_optional_secret calls above surface the warning at deploy time.

for layer in "${LAYERS[@]}"; do
  if [[ ! -d "$ROOT/$layer" ]]; then
    log "$layer — leeg, skip (wordt in latere fase ingevuld)"
    continue
  fi

  # platform/11-airflow contains the dbt-manifest-render Job, whose
  # git-sync initContainer reads GITSYNC_REPO from ConfigMap odap-repo-url
  # (optional key). Without it, git-sync exits "required flag: --repo"
  # and the Job fails — noisy and confusing, even though the same
  # manifest gets seeded later via the Docker-based renderer below.
  # Seed the ConfigMap from `git remote get-url origin` so the Job runs
  # to completion. Skip silently if git or the remote is missing.
  if [[ "$layer" == "platform/11-airflow" ]]; then
    repo_url="$(git -C "$ROOT" remote get-url origin 2>/dev/null || true)"
    if [[ -n "$repo_url" ]]; then
      kubectl -n odap-platform create configmap odap-repo-url \
        --from-literal=url="$repo_url" \
        --dry-run=client -o yaml | kubectl apply -f - >/dev/null
      log "  odap-repo-url ConfigMap geseed met ${repo_url} (voor dbt-manifest-render Job)"
    fi
  fi

  # Prefer mode-specific overlay; fall back to flat layout for components
  # that haven't been restructured yet.
  target="$(kustomize_overlay "$layer")"
  if find "$target" -maxdepth 2 -name '*.yaml' 2>/dev/null | grep -q .; then
    log "Apply $layer (mode=$DEPLOYMENT_MODE, kustomize=${target#$ROOT/})"
    kubectl apply -k "$target" 2>/dev/null \
      || kubectl apply -f "$target/" --recursive
  else
    log "$layer — leeg, skip"
  fi
done

# openmetadata-platform-config wordt door kustomize in `odap-meta` aangemaakt
# (zie platform/13-openmetadata-config/kustomization.yaml: configMapGenerator
# heeft `namespace: odap-meta`). De governance_om_ingest DAG en de KPO-tasks
# in 13-openmetadata-config/*-cronjob.yaml draaien echter in `odap-platform`
# en mounten de CM uit hun eigen namespace. Zonder deze copy-stap blijft
# de `odap-platform`-kopie stale na elke YAML-update onder services/ —
# bootstrap.sh doet 'm één keer bij eerste install, maar incremental
# deploys moeten 'm hier opnieuw doen.
mirror_om_config_cm() {
  if kubectl -n odap-meta get configmap openmetadata-platform-config >/dev/null 2>&1; then
    kubectl -n odap-meta get configmap openmetadata-platform-config -o yaml \
      | sed -e 's/namespace: odap-meta/namespace: odap/' \
            -e '/resourceVersion:/d' -e '/uid:/d' -e '/creationTimestamp:/d' \
      | kubectl apply -f - >/dev/null \
      && log "  openmetadata-platform-config gespiegeld naar odap-platform" \
      || printf '\033[1;33m!!\033[0m mirror van openmetadata-platform-config naar odap-platform faalde\n'
  fi
}
mirror_om_config_cm

# CoreDNS-override voor in-cluster resolutie van *.odap.local.
# Achtergrond: k3d kopieert de host-/etc/hosts naar de cluster-resolver
# zodat alle hostnames die de gebruiker daar heeft staan (127.0.0.1
# minio-console.odap.local etc.) ook in de pods naar 127.0.0.1
# wijzen. Voor MinIO/OpenMetadata/Superset/Airflow/Trino/NiFi die
# server-side OIDC-discovery doen tegen https://keycloak.odap.local:8443
# is dat fataal — ze proberen verbinding te maken met hun eigen loopback.
# Fix: laat CoreDNS *.odap.local naar de keycloak-external Service
# in ingress-nginx wijzen (die mappt 8443 → 443 op ingress-nginx-controller).
# platform-ca-bundle uitbreiden met de Stackable secret-operator self-signed CA.
# Bootstrap probeert dit ook (via een trigger-pod), maar als de operator dan
# nog niet klaar is om certs uit te delen, blijft de bundle alleen het
# platform-issuer CA en faalt later TLS-verify naar Trino/Hive
# (Superset → Trino, OM Java truststore, etc). Hier zijn alle pods al
# een tijdje TLS aan het opvragen, dus secret-provisioner-tls-ca bestaat.
log "platform-ca-bundle (her)opbouwen: Mozilla public roots + Platform CA + Stackable secret-operator CA"
# Public roots zijn nodig zodat Airflow/Superset/Trino (Python REQUESTS_CA_BUNDLE
# en SSL_CERT_FILE wijzen naar /etc/platform-ca/ca.crt) Let's Encrypt certs van
# keycloak.example.com kunnen verifiëren bij OIDC-token-
# exchange. Zonder die roots → "unable to get local issuer certificate".
# Platform CA is voor cert-manager-issued Keycloak op .local + interne TLS.
# Stackable-CA is voor in-cluster Trino/Hive/Kafka TLS (Superset → Trino).
if kubectl -n stackable-operators get secret secret-provisioner-tls-ca >/dev/null 2>&1; then
  TMP=$(mktemp -d)
  curl -fsSL --connect-timeout 10 https://curl.se/ca/cacert.pem -o "$TMP/public.crt"
  kubectl -n cert-manager get secret odap-platform-ca -o jsonpath='{.data.ca\.crt}' 2>/dev/null \
    | base64 -d > "$TMP/uwv.crt"
  kubectl -n stackable-operators get secret secret-provisioner-tls-ca \
    -o jsonpath='{.data.0\.ca\.crt}' | base64 -d > "$TMP/stackable.crt"
  if [[ -s "$TMP/public.crt" && -s "$TMP/uwv.crt" && -s "$TMP/stackable.crt" ]]; then
    cat "$TMP/public.crt" "$TMP/uwv.crt" "$TMP/stackable.crt" > "$TMP/combined.crt"
    # delete+create (apply hits 256KB last-applied-configuration annotation
    # limit — the combined bundle is ~220 KB).
    kubectl -n odap-platform delete configmap platform-ca-bundle --ignore-not-found >/dev/null
    kubectl -n odap-platform create configmap platform-ca-bundle \
      --from-file=ca.crt="$TMP/combined.crt" >/dev/null
    kubectl -n odap-meta delete configmap platform-ca-bundle --ignore-not-found >/dev/null
    kubectl -n odap-meta create configmap platform-ca-bundle \
      --from-file=ca.crt="$TMP/combined.crt" >/dev/null
    n=$(grep -c "BEGIN CERT" "$TMP/combined.crt")
    printf '\033[1;32mOK\033[0m platform-ca-bundle bevat nu %s certs (Mozilla + UWV + Stackable)\n' "$n"
    # Roll workloads die de bundle mounten, zodat hun proces de nieuwe file
    # ziet (de mounted file via ConfigMap-volume update zelf automatisch,
    # maar Python's `ssl` cached zijn context bij eerste open).
    kubectl -n odap-platform delete pod -l app.kubernetes.io/name=superset --ignore-not-found >/dev/null 2>&1 || true
    kubectl -n odap-platform delete pod -l app.kubernetes.io/name=airflow --ignore-not-found >/dev/null 2>&1 || true
    kubectl -n odap-meta delete pod -l app.kubernetes.io/name=openmetadata --ignore-not-found >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP"
else
  printf '\033[1;33m!!\033[0m secret-provisioner-tls-ca nog niet aanwezig (Stackable operators staan nog niet TLS uit te delen?). Re-run deploy-platform later.\n'
fi

if [[ "${IS_LOCAL}" == "yes" ]]; then
  log "CoreDNS-override voor *.${PLATFORM_DOMAIN} (mode=${DEPLOYMENT_MODE})"
  KC_SVC_IP=""
  for i in {1..30}; do
    KC_SVC_IP=$(kubectl -n ingress-nginx get svc keycloak-external -o jsonpath='{.spec.clusterIP}' 2>/dev/null || true)
    [[ -n "$KC_SVC_IP" && "$KC_SVC_IP" != "None" ]] && break
    sleep 2
  done
  if [[ -z "$KC_SVC_IP" || "$KC_SVC_IP" == "None" ]]; then
    printf '\033[1;33m!!\033[0m keycloak-external Service nog niet beschikbaar; CoreDNS-override overgeslagen\n'
  else
    # k3d: rewrite *.${PLATFORM_DOMAIN} naar de keycloak-external ClusterIP
    # zodat in-cluster OIDC-discovery van MinIO/Trino/Superset/Airflow/NiFi/
    # OpenMetadata werkt zonder /etc/hosts loopback.
    # IN AAAA-template levert NOERROR (lege answer-set) zodat Go's parallel
    # A+AAAA resolver geen SERVFAIL ziet — anders crasht de Grafana OIDC
    # token-exchange met "lookup keycloak.<domain>: Try again" (en NSS/getent
    # verbergt het probleem). Zie ook scripts/bootstrap.sh CoreDNS-block.
    coredns_zone=$(printf '%s' "$PLATFORM_DOMAIN" | sed 's/\./\\./g')
    kubectl -n kube-system create configmap coredns-custom --from-literal="${PLATFORM_DOMAIN}.server=${PLATFORM_DOMAIN}:53 {
    errors
    cache 30
    template IN A ${PLATFORM_DOMAIN} {
        match .*\\.${coredns_zone}
        answer \"{{ .Name }} 60 IN A ${KC_SVC_IP}\"
        fallthrough
    }
    template IN AAAA ${PLATFORM_DOMAIN} {
        match .*\\.${coredns_zone}
        rcode NOERROR
        fallthrough
    }
}
" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    kubectl -n kube-system rollout restart deployment coredns >/dev/null
    kubectl -n kube-system rollout status deployment coredns --timeout=60s >/dev/null
    printf '\033[1;32mOK\033[0m CoreDNS routet *.%s → %s (keycloak-external Service)\n' "$PLATFORM_DOMAIN" "$KC_SVC_IP"
  fi
else
  log "CoreDNS-override skipped (mode=${DEPLOYMENT_MODE}, handled by aks-deploy.sh)"
fi

# MinIO laadt OIDC-config alleen bij startup. Als de pod bootte vóór dat
# keycloak.odap.local resolveerbaar was (CoreDNS-override boven),
# faalt de eerste OpenID-discovery met "connection refused" en MinIO valt
# terug op `loginStrategy: form` — geen Keycloak-knop op de console of
# /go/minio/ portal-redirect. Restart pakt OIDC opnieuw op.
log "MinIO restarten zodat OIDC-discovery via Keycloak slaagt"
kubectl -n odap-platform delete pod -l app=minio --ignore-not-found >/dev/null 2>&1 || true

# Live Keycloak runtime patches die niet uit de realm-import komen.
# Realm-import strategy=IGNORE_EXISTING raakt bestaande users niet aan; en
# attributen op users zoals `policy=consoleAdmin` (vereist door MinIO's
# `MINIO_IDENTITY_OPENID_CLAIM_NAME=policy` claim-mapper) zitten niet
# standaard in de import. Dezelfde stap zit in scripts/full-deploy.sh §8.
log "Keycloak: TOTP wissen + policy=consoleAdmin op demo-admins"
if kubectl -n odap-auth get pod keycloak-0 >/dev/null 2>&1; then
  kubectl -n odap-auth exec keycloak-0 -c keycloak -- bash -c '
T=$(curl -fsS -d "client_id=admin-cli" -d "username=kcadmin" -d "password=odap-dev-only-CHANGE-ME" -d "grant_type=password" http://localhost:8080/realms/master/protocol/openid-connect/token 2>/dev/null | sed "s/.*access_token\":\"\([^\"]*\)\".*/\1/")
[ -z "$T" ] && { echo "Keycloak admin login faalde"; exit 0; }
A="Authorization: Bearer $T"
KC=http://localhost:8080
for u in platform.admin wia.beoordelaar wajong.arbeidsdeskundige data.engineer; do
  KCUID=$(curl -fsS -H "$A" "$KC/admin/realms/odap/users?username=$u" 2>/dev/null | grep -oE "\"id\":\"[^\"]*\"" | head -1 | cut -d"\"" -f4)
  [ -z "$KCUID" ] && continue
  curl -sS -X PUT -H "$A" -H "Content-Type: application/json" "$KC/admin/realms/odap/users/$KCUID" \
    -d "{\"username\":\"$u\",\"email\":\"$u@odap.local\",\"emailVerified\":true,\"enabled\":true,\"requiredActions\":[],\"attributes\":{\"policy\":[\"consoleAdmin\"]}}" -o /dev/null
  curl -sS -X DELETE -H "$A" "$KC/admin/realms/odap/attack-detection/brute-force/users/$KCUID" -o /dev/null
done

# Idempotent: ensure the `jupyter` OIDC client (JupyterHub) exists. The
# client is in realm.json, but Keycloak imports with strategy
# IGNORE_EXISTING, so when the realm already exists from a previous deploy
# the new client is *not* added — leading to "Client not found" at login.
EXISTS=$(curl -fsS -H "$A" "$KC/admin/realms/odap/clients?clientId=jupyter" 2>/dev/null)
if echo "$EXISTS" | grep -q "\"clientId\":\"jupyter\""; then
  echo "jupyter client already present"
else
  curl -sS -X POST -H "$A" -H "Content-Type: application/json" \
    "$KC/admin/realms/odap/clients" \
    -d "{\"clientId\":\"jupyter\",\"name\":\"ODAP Lab (Jupyter)\",\"enabled\":true,\"protocol\":\"openid-connect\",\"publicClient\":false,\"secret\":\"odap-dev-only-CHANGE-ME-jupyter-secret\",\"standardFlowEnabled\":true,\"directAccessGrantsEnabled\":false,\"serviceAccountsEnabled\":false,\"redirectUris\":[\"https://jupyter.'"${PLATFORM_DOMAIN}"':'"${PLATFORM_PORT}"'/hub/oauth_callback\",\"https://jupyter.'"${PLATFORM_DOMAIN}"'/hub/oauth_callback\"],\"webOrigins\":[\"https://jupyter.'"${PLATFORM_DOMAIN}"':'"${PLATFORM_PORT}"'\",\"https://jupyter.'"${PLATFORM_DOMAIN}"'\"],\"defaultClientScopes\":[\"web-origins\",\"profile\",\"roles\",\"email\"],\"fullScopeAllowed\":true}" \
    -o /dev/null -w "jupyter client created (status %{http_code})\n"
fi
echo "Keycloak runtime patches OK"
' 2>&1 | tail -3
fi

# Superset: na eerste OIDC-login krijgen platform users de `Public`-rol.
# AUTH_ROLES_SYNC_AT_LOGIN promoot via realm_access.roles als die in de
# access_token zit; in deze realm zit die niet altijd, dus we promoten
# alle Public-only users handmatig naar Admin (demo-cluster only).
log "Superset: Admin-rol op demo-users zonder rollen"
# Use a Ready-check rather than just `get pod` — see DAG-unpause block below.
if kubectl -n odap-platform wait --for=condition=Ready pod/superset-node-default-0 --timeout=1s >/dev/null 2>&1; then
  kubectl -n odap-platform exec superset-node-default-0 -c superset -- python3 -c '
from superset.app import create_app
app = create_app()
with app.app_context():
    from flask_appbuilder.security.sqla.models import User, Role
    from superset import db
    admin = db.session.query(Role).filter_by(name="Admin").first()
    if not admin:
        print("Admin role missing — Superset niet geïnitialiseerd?")
    else:
        for u in db.session.query(User).all():
            if not u.roles or all(r.name == "Public" for r in u.roles):
                u.roles = [admin]
                db.session.commit()
                print(f"upgraded {u.username} -> Admin")
' 2>&1 | tail -10 || true
fi

# dbt-manifest ConfigMap voor Cosmos LoadMode.DBT_MANIFEST.
# De originele dbt-manifest-render Job (platform/11-airflow/jobs/) gebruikt
# git-sync tegen een private GitHub-repo, en het rauwe manifest.json (~1.4MB)
# overschrijdt de ConfigMap data-limiet (1MB). De Airflow-scheduler heeft
# echter al een `manifest-decompress` initContainer die `manifest.json.gz`
# en `dbt-project.tar.gz` uit binaryData uitpakt — we leveren die hier
# direct vanaf de host via de odap/dbt-trino:1.9.0 image (~135KB gzipd).
# Superset-init Job re-runt zodat hij na de CA-bundle update + Superset
# pod-roll de Trino-databases registreert. Backoff van een eerdere Failed
# Job blokkeert anders een retry.
log "superset-init Job opnieuw triggeren (na CA-bundle update + pod-roll)"
kubectl -n odap-platform delete job superset-init --ignore-not-found >/dev/null 2>&1 || true
kubectl apply -k "$ROOT/platform/12-superset" >/dev/null 2>&1 || true

# OpenMetadata: seed admin JWT + re-trigger openmetadata-init Job.
# Bootstrap probeert dit ook (fail-soft), maar OM is dan vaak nog niet up
# → JWT-secret blijft leeg → openmetadata-init API-calls krijgen 401
# en classifications/glossary worden niet geladen. Hier is OM Ready.
log "OpenMetadata: decrypt ingestion-bot JWT + re-trigger init-Job"
if kubectl -n odap-meta rollout status deploy/openmetadata --timeout=5m >/dev/null 2>&1; then
  FERNET=$(kubectl -n odap-meta get secret openmetadata-fernetkey-secret -o jsonpath='{.data}' 2>/dev/null \
    | python3 -c 'import json,sys,base64;d=json.load(sys.stdin);print(next(iter(base64.b64decode(v).decode() for v in d.values())))' 2>/dev/null || true)
  ENCRYPTED=$(kubectl -n odap-data exec postgres-postgresql-0 -c postgresql -- \
    env PGPASSWORD="$(kubectl -n odap-data get secret postgres-postgresql -o jsonpath='{.data.password}' | base64 -d)" \
    psql -U postgres -d openmetadata -t -A -c \
    "SELECT json->'authenticationMechanism'->'config'->>'JWTToken' FROM user_entity WHERE name='ingestion-bot' LIMIT 1;" \
    2>/dev/null | sed 's/^fernet://' || true)
  JWT=""
  if [[ -n "$FERNET" && -n "$ENCRYPTED" ]]; then
    JWT=$(python3 -c "
from cryptography.fernet import MultiFernet, Fernet
mf = MultiFernet([Fernet(k.encode()) for k in '${FERNET}'.split(',')])
print(mf.decrypt(b'${ENCRYPTED}').decode())
" 2>/dev/null || true)
  fi
  if [[ -n "$JWT" ]]; then
    JWT_B64=$(printf '%s' "$JWT" | base64 | tr -d '\n')
    kubectl -n odap-meta patch secret openmetadata-admin --type='json' \
      -p="[{\"op\":\"replace\",\"path\":\"/data/jwtToken\",\"value\":\"${JWT_B64}\"}]" >/dev/null 2>&1 || true
    kubectl -n odap-platform create secret generic openmetadata-admin \
      --from-literal=jwtToken="$JWT" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    kubectl -n odap-meta delete job openmetadata-init --ignore-not-found >/dev/null 2>&1 || true
    kubectl apply -k "$ROOT/platform/13-openmetadata-config" >/dev/null 2>&1 || true
    # De re-apply hierboven update de CM in odap-meta; mirror opnieuw naar
    # odap-platform zodat de DAG/CronJobs de verse YAML zien (zie helper).
    mirror_om_config_cm
    printf '\033[1;32mOK\033[0m OpenMetadata admin-JWT geseed + init-Job opnieuw getriggerd\n'
  else
    printf '\033[1;33m!!\033[0m JWT-decrypt faalde (OM nog niet klaar?) — re-run deploy-platform later\n'
  fi
else
  printf '\033[1;33m!!\033[0m OpenMetadata deployment niet Ready binnen 5m — JWT-seed overgeslagen\n'
fi

log "dbt-manifest ConfigMap renderen via odap/dbt-trino:1.9.0"
if docker image inspect odap/dbt-trino:1.9.0 >/dev/null 2>&1; then
  TMP=$(mktemp -d)
  docker run --rm -v "$TMP:/out" --entrypoint sh odap/dbt-trino:1.9.0 -c '
    cd /opt/odap/dbt
    cp profiles.yml.template profiles.yml 2>/dev/null || true
    DBT_PROFILES_DIR=/opt/odap/dbt \
    TRINO_HOST=placeholder TRINO_PORT=8443 \
    TRINO_USER=placeholder TRINO_PASSWORD=placeholder \
    TABLE_FORMAT=delta \
    dbt parse --target dev >/tmp/dbt.log 2>&1 || cat /tmp/dbt.log >&2
    cp target/manifest.json /out/manifest.json 2>/dev/null || true
    # NB: --exclude pattern moet `./<naam>` zijn (niet kale `<naam>`) en
    # vóór de bron staan. .venv (~107MB) sluipt anders mee uit nieuwere
    # dbt-images en blaast de tarball over de 3MB etcd-record-limiet.
    tar -czf /out/dbt-project.tar.gz \
      --exclude=./target --exclude=./logs --exclude=./dbt_packages \
      --exclude=./.venv --exclude=./.user.yml --exclude=./.dockerignore \
      . 2>/dev/null
  ' 2>&1 | tail -3 || true
  if [[ -s "$TMP/manifest.json" ]]; then
    gzip -f -c "$TMP/manifest.json" > "$TMP/manifest.json.gz"
    kubectl -n odap-platform create configmap dbt-manifest \
      --from-file=manifest.json.gz="$TMP/manifest.json.gz" \
      --from-file=dbt-project.tar.gz="$TMP/dbt-project.tar.gz" \
      --dry-run=client -o yaml | kubectl apply -f - >/dev/null
    # Forceer Airflow scheduler-rollout zodat manifest-decompress init opnieuw runt.
    kubectl -n odap-platform delete pod -l app.kubernetes.io/component=scheduler --ignore-not-found >/dev/null 2>&1 || true
    printf '\033[1;32mOK\033[0m dbt-manifest ConfigMap geseed (manifest.json.gz=%s, dbt-project.tar.gz=%s)\n' \
      "$(du -h "$TMP/manifest.json.gz" | cut -f1)" "$(du -h "$TMP/dbt-project.tar.gz" | cut -f1)"
  else
    printf '\033[1;33m!!\033[0m dbt parse leverde geen manifest.json op — Cosmos draait in fallback (lege DAG-set)\n'
  fi
  rm -rf "$TMP"
else
  printf '\033[1;33m!!\033[0m odap/dbt-trino:1.9.0 image niet gevonden — `make dbt-image` eerst draaien\n'
fi

# Unpause de Platform DAGs so they automatically start on their cron schedule once
# de scheduler ze ziet. Airflow's default is is_paused_upon_creation=true,
# en op een verse cluster betekent dat ze stilstaan tot je via de UI klikt.
log "Unpause Platform DAGs (governance/ingest/transform/maintenance)"
# Pod-readiness gate: `kubectl get pod` succeeds even when the pod is
# pending/no-host (the resource exists). With `set -o pipefail` an
# `exec` failure here aborts the whole script. Use a `Ready` check.
if kubectl -n odap-platform wait --for=condition=Ready pod/airflow-scheduler-default-0 --timeout=1s >/dev/null 2>&1; then
  kubectl -n odap-platform exec airflow-scheduler-default-0 -c airflow -- bash -c '
for dag in bronze_watch \
           silver_persoon silver_polisadm silver_ww silver_wia \
           silver_wajong silver_zw silver_crm silver_fez silver_klantcontact \
           gold_uc01_wia_funnel gold_uc04_tw_eligibility gold_uc05_client_360 \
           gold_uc06_lastprognose gold_uc07_dq_polisadm gold_uc09_reint_effect \
           gold_uc_klant_tev_klanttevredenheid \
           governance_om_ingest bewaartermijn_enforcer lakehouse_maintenance; do
  airflow dags unpause "$dag" >/dev/null 2>&1 || true
done
echo "DAGs unpaused (skipped any that don'\''t exist yet — parse delay is normal)"
  ' 2>&1 | tail -2 || true
else
  printf '\033[1;33m!!\033[0m airflow-scheduler-default-0 nog niet ready — DAGs blijven paused tot je manueel `airflow dags unpause` draait\n'
fi

# om-access-bridge (ADR-0008): self-service data-access webhook bridge.
#
# Was eerder een opt-in `make deploy-om-bridge` target omdat het de OM admin
# JWT moet seeden, en die JWT bestaat pas nadat OpenMetadata up is. We
# wachten kort tot dat secret er is en draaien dan de bridge-deploy.
# Faalt elegant als OM nog niet ready is — gebruiker krijgt een waarschuwing
# met de hint om `make deploy-om-bridge` zelf te draaien.
log "om-access-bridge (ADR-0008): wait for OM admin token, then deploy"
om_ready=false
for i in 1 2 3 4 5 6; do
  if kubectl -n odap-meta get secret openmetadata-admin -o jsonpath='{.data.jwtToken}' 2>/dev/null | grep -q .; then
    om_ready=true
    break
  fi
  sleep 5
done
if $om_ready; then
  if [[ "${SKIP_OM_BRIDGE:-}" == "1" ]]; then
    log "  SKIP_OM_BRIDGE=1 gezet — om-access-bridge wordt niet gedeployd"
  elif command -v make >/dev/null && [[ -f "$ROOT/Makefile" ]]; then
    (cd "$ROOT" && make deploy-om-bridge MODE="${MODE:-k3d}" 2>&1) | sed 's/^/  /' || \
      printf '\033[1;33m!!\033[0m om-access-bridge deploy gefaald — run `make deploy-om-bridge` handmatig\n'
  else
    printf '\033[1;33m!!\033[0m make/Makefile niet beschikbaar — run `make deploy-om-bridge` handmatig\n'
  fi
else
  printf '\033[1;33m!!\033[0m openmetadata-admin secret nog niet aanwezig na 30s — '
  printf 'om-access-bridge overgeslagen. Run `make deploy-om-bridge` zodra OM ready is.\n'
fi

log "Deploy-platform fase 1 stub klaar."
echo "Run wordt pas zinvol vanaf fase 2. Zie WORKLOG.md."
