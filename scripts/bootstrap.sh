#!/usr/bin/env bash
# Bootstrap — installeer Helm-charts en Stackable-operators op een lege cluster.
#
# Mode: k3d (default) of aks. Selectie via --mode=<mode> of
# DEPLOYMENT_MODE env. Per-chart values worden gestapeld:
#   infrastructure/helm/<chart>/values.yaml          (mode-agnostic base)
#   infrastructure/helm/<chart>/values-<mode>.yaml   (mode-specific overlay)
#
# Volgorde:
#   1. cert-manager (CRDs first, --wait)
#   2. ClusterIssuer (self-signed CA voor *.${PLATFORM_DOMAIN})
#   3. ingress-nginx
#   4. PostgreSQL (gedeeld voor HMS, Airflow, Superset, OpenMetadata, Keycloak)
#   5. MinIO (S3-compatible, single-node)
#   6. Keycloak (OIDC IdP, met ODAP realm via ConfigMap-import)
#   7. Prometheus stack (incl. Grafana)
#   8. Stackable Data Platform 26.3 operators
#
# Idempotent: helm upgrade --install per chart; ConfigMaps en kubectl apply
# zijn ook idempotent.
#
# Eindresultaat: alle kruisbestuiving-services draaien; Stackable-CRDs zijn
# beschikbaar; klaar voor `make deploy-platform` (fase 2+).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Mode handling (--mode, DEPLOYMENT_MODE, context validation, PLATFORM_DOMAIN).
# shellcheck source=lib/mode.sh
source "${ROOT}/scripts/lib/mode.sh"
parse_mode_args "$@"
require_context
require_storage_class

# Versies — bewust vastgepind; updates via PR.
CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.16.2}"
INGRESS_NGINX_VERSION="${INGRESS_NGINX_VERSION:-4.11.3}"
POSTGRES_VERSION="${POSTGRES_VERSION:-16.0.6}"
MINIO_VERSION="${MINIO_VERSION:-5.3.0}"
KEYCLOAK_VERSION="${KEYCLOAK_VERSION:-22.2.6}"
PROM_VERSION="${PROM_VERSION:-65.5.1}"
OPENSEARCH_VERSION="${OPENSEARCH_VERSION:-2.27.1}"
OPENSEARCH_DASHBOARDS_VERSION="${OPENSEARCH_DASHBOARDS_VERSION:-2.26.0}"
OPENMETADATA_VERSION="${OPENMETADATA_VERSION:-1.12.8}"
VECTOR_VERSION="${VECTOR_VERSION:-0.36.1}"

# Prerequisites check
command -v helm >/dev/null     || error "helm niet gevonden"
command -v kubectl >/dev/null  || error "kubectl niet gevonden"
command -v stackablectl >/dev/null || error "stackablectl niet gevonden — zie scripts/doctor.sh"

warn "Dev-only credentials in dit bootstrap. NIET gebruiken in production. Zie infrastructure/helm/*/values.yaml."

# 0a. Persistente CA on the host (één keer gegenereerd, hergebruikt op elke
# bootstrap). Geseed't in stap 1b naar Secret odap-platform-ca; cert-manager's
# platform-issuer tekent alle leaf-certs ermee. Doordat de CA *niet*
# regenereert op `make clean && make cluster && make bootstrap`, blijft de
# in je OS-keychain vertrouwde CA (`make trust-ca`) geldig over cluster-wipes.
CA_DIR="${CA_DIR:-${HOME}/.config/odap/ca}"
CA_CRT="${CA_DIR}/tls.crt"
CA_KEY="${CA_DIR}/tls.key"

if [[ ! -f "$CA_CRT" || ! -f "$CA_KEY" ]]; then
  log "Genereer persistente CA in ${CA_DIR}"
  mkdir -p "$CA_DIR"
  chmod 700 "$CA_DIR"
  # ECDSA P-256, 10 jaar, basicConstraints CA:TRUE — match het profiel dat
  # cert-manager voorheen genereerde via cluster-issuer.yaml.
  openssl ecparam -name prime256v1 -genkey -noout -out "$CA_KEY"
  openssl req -x509 -new -nodes -key "$CA_KEY" -sha256 -days 3650 \
    -subj "/O=Open Data & Analytics Platform/O=Dev \\/ Self-Signed/CN=Open Data & Analytics Platform Self-Signed CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -out "$CA_CRT"
  chmod 600 "$CA_KEY"
  warn "Eerste run: import de CA met 'make trust-ca' om de browser-warning weg te krijgen."
else
  log "Hergebruik persistente CA uit ${CA_DIR}"
fi

# Spiegelkopie voor bestaande Makefile-conventie ($HOME/.odap-platform-ca.crt
# wordt door `make dbt-docs` als REQUESTS_CA_BUNDLE gebruikt).
cp "$CA_CRT" "${HOME}/.odap-platform-ca.crt"

# 0. Helm repo's
log "Helm repos toevoegen / updaten"
helm repo add jetstack https://charts.jetstack.io >/dev/null
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null
helm repo add bitnami https://charts.bitnami.com/bitnami >/dev/null
helm repo add minio https://charts.min.io/ >/dev/null
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo add opensearch https://opensearch-project.github.io/helm-charts/ >/dev/null
helm repo add open-metadata https://helm.open-metadata.org/ >/dev/null
helm repo add vector https://helm.vector.dev >/dev/null
helm repo update >/dev/null

# 1. cert-manager
log "Install cert-manager ${CERT_MANAGER_VERSION}"
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --version "${CERT_MANAGER_VERSION}" \
  $(chart_value_args cert-manager) \
  --force-conflicts \
  --wait --timeout 5m

# 1a. Legacy cleanup: oude cert-manager-managed CA-Certificate (uit een
# eerdere versie van cluster-issuer.yaml). Verwijderen voorkomt dat
# cert-manager onze host-managed Secret in stap 1b overschrijft.
kubectl -n cert-manager delete certificate odap-platform-ca --ignore-not-found=true >/dev/null 2>&1 || true
kubectl delete clusterissuer selfsigned-bootstrap --ignore-not-found=true >/dev/null 2>&1 || true

# 1b. CA-Secret zaaien vanuit ${CA_DIR}. cert-manager's CA-issuer leest
# tls.crt + tls.key uit dit Secret om alle leaf-certs te tekenen.
# Detecteer eerst of de CA in de cluster afwijkt van de host-CA — als dat zo
# is moeten leaf-certs opnieuw worden uitgegeven (stap 2a).
PREV_CLUSTER_CA="$(kubectl -n cert-manager get secret odap-platform-ca \
  -o jsonpath='{.data.tls\.crt}' 2>/dev/null | base64 -d 2>/dev/null || true)"
HOST_CA_BODY="$(cat "$CA_CRT")"
CA_CHANGED="no"
if [[ -n "$PREV_CLUSTER_CA" && "$PREV_CLUSTER_CA" != "$HOST_CA_BODY" ]]; then
  CA_CHANGED="yes"
  warn "Cluster-CA wijkt af van host-CA — leaf-certs worden opnieuw uitgegeven."
fi

log "Apply odap-platform CA secret (vanuit ${CA_DIR})"
kubectl create secret tls odap-platform-ca \
  --namespace cert-manager \
  --cert="$CA_CRT" \
  --key="$CA_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. ClusterIssuer (na cert-manager — CRDs moeten ready zijn)
log "Apply odap-platform ClusterIssuer (host-managed CA)"
# Wacht expliciet tot de CRD bestaat (cert-manager helm --wait dekt dit, maar zekerheid)
kubectl wait --for=condition=Established crd/clusterissuers.cert-manager.io --timeout=2m
kubectl apply -f "${ROOT}/infrastructure/helm/cert-manager/cluster-issuer.yaml"

# 2a. Re-issue leaf-certs als de CA is veranderd. cert-manager regenereert
# elk Secret automatisch zodra het verdwijnt, getekend through the huidige CA.
if [[ "$CA_CHANGED" == "yes" ]]; then
  log "Re-issue leaf-certs door platform-issuer"
  kubectl get certificates -A \
    -o jsonpath='{range .items[?(@.spec.issuerRef.name=="platform-issuer")]}{.metadata.namespace}{" "}{.spec.secretName}{"\n"}{end}' \
    | while read -r ns secret; do
        [[ -z "$ns" || -z "$secret" ]] && continue
        kubectl -n "$ns" delete secret "$secret" --ignore-not-found=true >/dev/null 2>&1 || true
      done
fi

# 3. ingress-nginx
log "Install ingress-nginx ${INGRESS_NGINX_VERSION}"
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --version "${INGRESS_NGINX_VERSION}" \
  $(chart_value_args ingress-nginx) \
  --wait --timeout 5m

# 3a. Extra port 8443 on the ingress-nginx-controller Service.
# Browsers gebruiken `*.odap.local:8443` (k3d port-mapt host:8443
# → node:443). Maar server-to-server-calls *binnen* de cluster zien geen
# host-mapping — die hebben dezelfde URL nodig om dezelfde plek te bereiken.
# Zonder deze patch faalt bv. OpenMetadata's OIDC-discovery naar Keycloak
# met "Connection refused" op poort 8443.
# Idempotent: alleen toevoegen als 8443 nog niet in de Service-spec staat.
log "Patch ingress-nginx-controller Service: voeg poort 8443 toe (in-cluster bereikbaarheid)"
if ! kubectl get svc -n ingress-nginx ingress-nginx-controller \
     -o jsonpath='{.spec.ports[?(@.port==8443)].port}' 2>/dev/null | grep -q 8443; then
  kubectl patch svc -n ingress-nginx ingress-nginx-controller --type=json \
    -p='[{"op":"add","path":"/spec/ports/-","value":{"name":"https-8443","port":8443,"protocol":"TCP","targetPort":"https","appProtocol":"https"}}]' \
    >/dev/null
fi

# 3b. CoreDNS-override voor *.${PLATFORM_DOMAIN}.
# Zonder deze override resolved een pod `keycloak.odap.local` via de
# upstream DNS van de host (de Mac's /etc/hosts), die alles naar 127.0.0.1
# mapped. Server-side OIDC-calls vanuit pods knallen dan op localhost en
# falen met "Connection refused".
# Fix: een CoreDNS server-block dat wildcard-matched to the ingress-nginx
# Service-ClusterIP. k3s mounts coredns-custom automatisch onder
# /etc/coredns/custom/ en het Corefile importeert *.server-files als
# extra server-blocks. ClusterIP wordt dynamisch ingelezen (kan per
# bootstrap variëren, k3d alloceert uit 10.43.0.0/16).
#
# Twee template-blocks:
#   - IN A: levert ClusterIP-record voor *.${PLATFORM_DOMAIN}
#   - IN AAAA: rcode NOERROR (lege answer-set). Zonder dit krijgt een AAAA-
#     query SERVFAIL — template matched alleen IN A en de fallthrough vindt
#     geen volgende plugin in dit server-block. Go's net.Resolver doet
#     parallel A+AAAA en faalt op SERVFAIL met "lookup ... Try again";
#     dat brak de Grafana OIDC token-exchange naar
#     keycloak.${PLATFORM_DOMAIN}. NSS/getent is tolerant en geeft de A
#     terug, dus handmatige tests met `getent hosts` lieten dit niet zien.
#     NOERROR is de juiste DNS-respons voor "host bestaat, geen AAAA".
if [[ "${IS_LOCAL:-yes}" == "yes" ]]; then
  log "Apply CoreDNS-override voor *.${PLATFORM_DOMAIN} → ingress-nginx ClusterIP"
  INGRESS_CLUSTERIP="$(kubectl get svc -n ingress-nginx ingress-nginx-controller \
    -o jsonpath='{.spec.clusterIP}')"
  DOMAIN_ESCAPED="$(echo "${PLATFORM_DOMAIN}" | sed 's/\./\\\\./g')"
  kubectl apply -f - <<EOF >/dev/null
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns-custom
  namespace: kube-system
data:
  uwv.server: |
    ${PLATFORM_DOMAIN}:53 {
        errors
        cache 30
        template IN A ${PLATFORM_DOMAIN} {
            match ^([a-zA-Z0-9-]+\.)?${DOMAIN_ESCAPED}\.\$
            answer "{{ .Name }} 60 IN A ${INGRESS_CLUSTERIP}"
            fallthrough
        }
        template IN AAAA ${PLATFORM_DOMAIN} {
            match ^([a-zA-Z0-9-]+\.)?${DOMAIN_ESCAPED}\.\$
            rcode NOERROR
            fallthrough
        }
    }
EOF
  kubectl rollout restart -n kube-system deploy/coredns >/dev/null
  kubectl rollout status -n kube-system deploy/coredns --timeout=60s >/dev/null
fi

# 4. PostgreSQL (shared)
log "Install PostgreSQL ${POSTGRES_VERSION} (gedeeld)"
kubectl create namespace odap-data --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install postgres bitnami/postgresql \
  --namespace odap-data \
  --version "${POSTGRES_VERSION}" \
  $(chart_value_args postgresql) \
  --atomic --wait --timeout 10m

# 4b. MinIO TLS-secret voorbereiden (vóór helm install minio).
# MinIO chart values pinnen `tls.certSecret: minio-tls-internal-fixed`,
# verwachten keys public.crt + private.key. cert-manager produceert
# tls.crt/tls.key. Daarom: maak Certificate, wacht op secret, re-key
# met juiste keynamen.
log "Prepare MinIO TLS secret via cert-manager"
kubectl create namespace odap-platform --dry-run=client -o yaml | kubectl apply -f - >/dev/null
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: minio-tls-internal
  namespace: odap-platform
spec:
  secretName: minio-tls-internal
  issuerRef:
    name: platform-issuer
    kind: ClusterIssuer
  commonName: minio.odap-platform.svc.cluster.local
  dnsNames:
    - minio.odap-platform.svc.cluster.local
    - minio.odap-platform.svc
    - minio
    - minio.${PLATFORM_DOMAIN}
  duration: 8760h
EOF
# Wacht tot Secret bestaat
for i in {1..30}; do
  kubectl -n odap-platform get secret minio-tls-internal >/dev/null 2>&1 && break
  sleep 2
done
# Re-key to the naam + sleutels die MinIO chart verwacht
TMPCRT=$(mktemp); TMPKEY=$(mktemp); TMPCA=$(mktemp)
kubectl -n odap-platform get secret minio-tls-internal -o jsonpath='{.data.tls\.crt}' | base64 -d > "$TMPCRT"
kubectl -n odap-platform get secret minio-tls-internal -o jsonpath='{.data.tls\.key}' | base64 -d > "$TMPKEY"
kubectl -n odap-platform get secret minio-tls-internal -o jsonpath='{.data.ca\.crt}' | base64 -d > "$TMPCA"
kubectl -n odap-platform create secret generic minio-tls-internal-fixed \
  --from-file=public.crt="$TMPCRT" --from-file=private.key="$TMPKEY" --from-file=ca.crt="$TMPCA" \
  --dry-run=client -o yaml | kubectl apply -f -
# CA-bundle voor S3Connection (Stackable Trino + Spark server-verify).
# tls.crt + tls.key zijn ook nodig: Stackable secret-operator levert deze
# in format `tls-pkcs12` (Spark eist PKCS12-truststore), wat een complete
# keypair in de bron-secret vereist — anders faalt PVC-mount op
# 'missing required file tls.crt'.
kubectl -n odap-platform create secret generic minio-ca-bundle \
  --from-file=ca.crt="$TMPCA" \
  --from-file=tls.crt="$TMPCRT" \
  --from-file=tls.key="$TMPKEY" \
  --dry-run=client -o yaml | \
  sed 's|^metadata:|metadata:\n  labels:\n    secrets.stackable.tech/class: minio-ca|' | \
  kubectl apply -f -
# platform-ca-bundle: initial bundle = UWV self-signed CA + public roots (Mozilla
# bundle from curl.se/cacert.pem). Public roots are required so workloads
# that point REQUESTS_CA_BUNDLE/SSL_CERT_FILE at /etc/platform-ca/ca.crt (Airflow,
# Superset) can verify Let's Encrypt-issued certs on
# {keycloak,airflow,...}.example.com. Without this, Airflow's
# OIDC token exchange fails with 'unable to get local issuer certificate'.
# Stackable secret-operator's CA gets appended further down this script.
#
# We use delete+create (not `apply`) because the bundle exceeds 256KB once
# concatenated; `apply` records the whole resource as a metadata annotation
# (limit 256 KB) and rejects it. Delete+create avoids that path.
TMPPUB=$(mktemp)
log "Fetching Mozilla CA bundle (public roots) for platform-ca-bundle"
curl -fsSL https://curl.se/ca/cacert.pem -o "$TMPPUB"
TMPCOMBINED=$(mktemp)
cat "$TMPPUB" "$TMPCA" > "$TMPCOMBINED"
kubectl -n odap-platform delete configmap platform-ca-bundle --ignore-not-found >/dev/null
kubectl -n odap-platform create configmap platform-ca-bundle \
  --from-file=ca.crt="$TMPCOMBINED" >/dev/null
rm -f "$TMPCRT" "$TMPKEY" "$TMPCA" "$TMPPUB" "$TMPCOMBINED"

# 5. MinIO
log "Install MinIO ${MINIO_VERSION}"
kubectl create namespace odap-platform --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install minio minio/minio \
  --namespace odap-platform \
  --version "${MINIO_VERSION}" \
  $(chart_value_args minio) \
  --atomic --wait --timeout 10m

# 6. Prometheus + Grafana — moet vóór Keycloak, want Keycloak's chart
# enabled=true op metrics.serviceMonitor referenceert de
# monitoring.coreos.com/v1 CRDs uit deze stack.
log "Install kube-prometheus-stack ${PROM_VERSION}"
kubectl create namespace odap-monitoring --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --namespace odap-monitoring \
  --version "${PROM_VERSION}" \
  $(chart_value_args prometheus-stack) \
  --atomic --wait --timeout 15m

# 6b. Postgres reconciliation — MUST land before Keycloak install.
# Op cloud-modes (aks/stackit) is de in-line `initdb.scripts.00-odap-databases.sql`
# uit values-{aks,stackit}.yaml genulld (Bitnami chart faalt stil bij eerste
# init op fresh cloud PVCs — zie values-aks.yaml). Het odap-role +
# de databases worden daardoor pas later aangemaakt door
# infrastructure/azure/postgres-create-databases.yaml. Maar Keycloak's chart
# verbindt direct na install met `odap@postgres`; als die user nog niet
# bestaat → StatefulSet crashloopt → helm --atomic rolt terug → bootstrap dood.
# Idempotent: ALTER USER + IF NOT EXISTS checks. Skip op k3d (local-path
# storage initdb werkt daar wel).
if [[ "${IS_CLOUD:-no}" == "yes" ]]; then
  log "Wait for postgres pod Ready (cloud-mode pre-Keycloak reconcile)"
  kubectl -n odap-data wait --for=condition=Ready pod -l app.kubernetes.io/name=postgresql --timeout=5m

  log "Reconcile postgres superuser password + odap role (idempotent)"
  PG_PW=$(kubectl -n odap-data get secret postgres-postgresql -o jsonpath='{.data.postgres-password}' | base64 -d)
  kubectl -n odap-data exec postgres-postgresql-0 -- env PGPASSWORD="${PG_PW}" \
    psql -U postgres -c "ALTER USER postgres WITH PASSWORD '${PG_PW}';" >/dev/null
  kubectl -n odap-data exec postgres-postgresql-0 -- env PGPASSWORD="${PG_PW}" bash -c \
    "psql -U postgres -tAc \"SELECT 1 FROM pg_roles WHERE rolname='odap'\" | grep -q 1 || \
     psql -U postgres -c \"CREATE USER odap WITH PASSWORD '${PG_PW}' CREATEDB;\""

  log "Apply postgres-create-databases Job (creates keycloak/superset/airflow/openmetadata/platform DBs)"
  kubectl apply -f "$ROOT/infrastructure/azure/postgres-create-databases.yaml"
  kubectl -n odap-data wait --for=condition=Complete job/postgres-create-databases --timeout=2m \
    || warn "postgres-create-databases Job did not complete; check 'kubectl -n odap-data logs job/postgres-create-databases'"
fi

# 7. Keycloak — eerst realm-ConfigMap, daarna chart die hem mountt
log "ConfigMap: Keycloak ODAP realm"
kubectl create namespace odap-auth --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap keycloak-realm \
  --namespace odap-auth \
  --from-file=odap-realm.json="${ROOT}/infrastructure/helm/keycloak/realm.json" \
  --dry-run=client -o yaml | kubectl apply -f -

log "Install Keycloak ${KEYCLOAK_VERSION}"
helm upgrade --install keycloak bitnami/keycloak \
  --namespace odap-auth \
  --version "${KEYCLOAK_VERSION}" \
  $(chart_value_args keycloak) \
  --atomic --wait --timeout 10m

# 8. Stackable operators
# Stackablectl 1.4+ heeft de `operator install --release-file` syntax laten
# vallen; we gebruiken nu de built-in 26.3 release. Custom pinning kan later
# via 'release install <name> -r <file>' (zie release.yaml).
log "Install Stackable operators (release 26.3)"
stackablectl release install 26.3 --operator-namespace stackable-operators

log "Wachten tot Stackable operator-pods aanwezig zijn (stackablectl returns before pods are scheduled)"
for i in {1..60}; do
  count=$(kubectl -n stackable-operators get pods --no-headers 2>/dev/null | wc -l)
  if [[ "$count" -gt 0 ]]; then break; fi
  sleep 2
done

log "Wachten tot Stackable operator-pods Ready zijn (timeout 5m)"
kubectl wait --for=condition=Ready pod -n stackable-operators \
  -l stackable.tech/vendor=Stackable \
  --timeout=5m || warn "Niet alle Stackable operator-pods zijn (nog) Ready — check 'kubectl get pods -A'"

# Stackable's "release 26.3" installs every operator (~18 deployments). On a
# single-node D8s_v6 with AKS default max-pods=60 that pushes us against the
# pod limit, blocking OpenSearch Dashboards from scheduling. We don't use
# Druid / HBase / HDFS / the Stackable opensearch operator (we install
# OpenSearch via the official Helm chart), so uninstall those 4 to free 4
# pod slots. Idempotent — safe to re-run.
log "Removing unused Stackable operators (druid, hbase, hdfs, opensearch) to stay under pod limit"
for op in druid-operator hbase-operator hdfs-operator opensearch-operator; do
  if helm -n stackable-operators status "$op" >/dev/null 2>&1; then
    helm -n stackable-operators uninstall "$op" >/dev/null 2>&1 || warn "Kon $op niet verwijderen"
  fi
done

# platform-ca-bundle uitbreiden with the Stackable secret-operator self-signed CA.
# Stackable Trino/Hive/Kafka/etc. krijgen pod-certs uit deze CA voor in-cluster
# TLS (tls-internal SecretClass). Zonder deze CA in de bundle weigeren clients
# als Superset (REQUESTS_CA_BUNDLE → /etc/platform-ca/ca.crt) een SQLAlchemy-
# verbinding naar https://trino-coordinator:8443 met
# 'self-signed certificate in certificate chain'. De originele odap-platform-
# issuer CA blijft staan voor extern verkeer (Keycloak via :8443 ingress).
#
# secret-provisioner-tls-ca wordt door secret-operator pas gegenereerd op
# eerste cert-request via de `tls` SecretClass. Forceer dat met een
# kortlevende Pod die zo'n volume mountt.
log "Trigger secret-provisioner-tls-ca generation via dummy CSI volume Pod"
kubectl -n stackable-operators delete pod tls-ca-trigger --ignore-not-found --wait=true >/dev/null 2>&1 || true
# secret-operator >= v26.3 only accepts CSI Persistent mode (not the older
# Ephemeral inline `csi:` volume). Use Kubernetes generic ephemeral volumes —
# a PVC is generated on demand and bound to the Pod's lifecycle, but the
# CSI sees it as a Persistent volume so secrets.stackable.tech is happy.
cat <<'EOF' | kubectl apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: tls-ca-trigger
  namespace: stackable-operators
spec:
  restartPolicy: Never
  terminationGracePeriodSeconds: 1
  containers:
  - name: idle
    image: registry.k8s.io/pause:3.9
    volumeMounts:
    - name: tls
      mountPath: /tls
  volumes:
  - name: tls
    ephemeral:
      volumeClaimTemplate:
        metadata:
          annotations:
            secrets.stackable.tech/class: tls
            secrets.stackable.tech/scope: pod
        spec:
          accessModes: [ReadWriteOnce]
          storageClassName: secrets.stackable.tech
          resources:
            requests:
              storage: 1Mi
EOF

log "Wachten tot secret-provisioner-tls-ca beschikbaar is (timeout 10m)"
SECRET_READY=false
for i in {1..300}; do
  if kubectl -n stackable-operators get secret secret-provisioner-tls-ca >/dev/null 2>&1; then
    SECRET_READY=true
    break
  fi
  sleep 2
done
kubectl -n stackable-operators delete pod tls-ca-trigger --ignore-not-found --wait=false >/dev/null 2>&1 || true

# Hard-fail als de CA niet beschikbaar is: zonder Stackable-CA in platform-ca-bundle
# weigert Superset (en andere clients met REQUESTS_CA_BUNDLE=/etc/platform-ca/ca.crt)
# elke TLS-verbinding naar Trino/Hive/Kafka met 'self-signed certificate in
# certificate chain'. Stille soft-fail leidde voorheen tot moeilijk te
# debuggen 500-errors in superset-init bij DB-registratie.
if [[ "$SECRET_READY" != "true" ]]; then
  error "secret-provisioner-tls-ca niet verschenen binnen 10m — secret-operator-pod waarschijnlijk niet healthy. Check 'kubectl -n stackable-operators get pods' en run bootstrap opnieuw."
fi

log "platform-ca-bundle extenden met Stackable secret-operator CA"
TMPCA=$(mktemp)
TMPCAS=$(mktemp)
kubectl -n odap-platform get cm platform-ca-bundle -o jsonpath='{.data.ca\.crt}' > "$TMPCA"
kubectl -n stackable-operators get secret secret-provisioner-tls-ca \
  -o jsonpath='{.data.0\.ca\.crt}' | base64 -d > "$TMPCAS"
cat "$TMPCA" "$TMPCAS" > "$TMPCA.combined"
# delete+create (apply hits 256KB annotation limit — bundle now contains
# 150+ public roots + Platform CA + Stackable CA).
kubectl -n odap-platform delete configmap platform-ca-bundle --ignore-not-found >/dev/null
kubectl -n odap-platform create configmap platform-ca-bundle \
  --from-file=ca.crt="$TMPCA.combined" >/dev/null
rm -f "$TMPCA" "$TMPCAS" "$TMPCA.combined"

# Sanity-check: bundle moet "secret-operator self-signed" subject bevatten.
# Decode the PEM bundle to human-readable form first — the literal CN string
# only appears in the ASN.1 (binary) of each cert, never in the base64 text.
# Plain `grep "secret-operator self-signed"` on the raw bundle is broken even
# when the cert IS present.
TMPBUNDLE=$(mktemp)
kubectl -n odap-platform get cm platform-ca-bundle -o jsonpath='{.data.ca\.crt}' > "$TMPBUNDLE"
if ! openssl crl2pkcs7 -nocrl -certfile "$TMPBUNDLE" 2>/dev/null \
   | openssl pkcs7 -print_certs -noout 2>/dev/null \
   | grep -q "secret-operator self-signed"; then
  rm -f "$TMPBUNDLE"
  error "platform-ca-bundle bevat na merge geen 'secret-operator self-signed' subject — CA-merge faalde stil."
fi
rm -f "$TMPBUNDLE"

# 9. OpenSearch single-node (gedeeld voor Vector logs + OpenMetadata search)
log "Install OpenSearch ${OPENSEARCH_VERSION} (single-node, odap-meta)"
kubectl create namespace odap-meta --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install opensearch opensearch/opensearch \
  --namespace odap-meta \
  --version "${OPENSEARCH_VERSION}" \
  $(chart_value_args opensearch) \
  --atomic --wait --timeout 10m

# 9a. OpenSearch Dashboards — UI voor logs (logs-*) en OM-search indices.
log "Install OpenSearch Dashboards ${OPENSEARCH_DASHBOARDS_VERSION} (odap-meta)"
helm upgrade --install opensearch-dashboards opensearch/opensearch-dashboards \
  --namespace odap-meta \
  --version "${OPENSEARCH_DASHBOARDS_VERSION}" \
  $(chart_value_args opensearch-dashboards) \
  --atomic --wait --timeout 10m

# 10. OpenMetadata
# Voor de OIDC-koppeling met Keycloak doet de OM-pod server-side een
# token-exchange tegen https://keycloak.odap.local:8443 (zelf-signed
# CA via platform-issuer). De pod's Java truststore krijgt die CA via
# een initContainer; daarvoor moet de platform-ca-bundle ConfigMap óók in de
# odap-meta namespace bestaan.
log "platform-ca-bundle ConfigMap kopiëren naar odap-meta (voor OM Java truststore)"
# delete+create — bundle is >256KB so `apply` rejects it (annotation limit).
TMPCAYAML=$(mktemp)
kubectl -n odap-platform get configmap platform-ca-bundle -o jsonpath='{.data.ca\.crt}' > "$TMPCAYAML"
kubectl -n odap-meta delete configmap platform-ca-bundle --ignore-not-found >/dev/null
kubectl -n odap-meta create configmap platform-ca-bundle --from-file=ca.crt="$TMPCAYAML" >/dev/null
rm -f "$TMPCAYAML"

# OpenMetadata helm-chart hardcodes db-credential secret naam `mysql-secrets`
# met key `openmetadata-mysql-password`, ook bij Postgres. Aanmaken vóór
# install zodat het Deployment niet faalt op missing secret-key.
log "OpenMetadata mysql-secrets (chart-quirk, ook voor Postgres-deploy)"
PG_PW=$(kubectl -n odap-data get secret postgres-postgresql -o jsonpath='{.data.password}' | base64 -d)
kubectl -n odap-meta create secret generic mysql-secrets \
  --from-literal=openmetadata-mysql-password="${PG_PW}" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# OpenMetadata Helm chart referencet `openmetadata-oidc-client` Secret in
# odap-meta (Keycloak SSO). Die zit in platform/01-secrets/dev-secrets.yaml en
# wordt normaal door deploy-platform aangemaakt — maar dat draait NÁ bootstrap.
# Pas alle dev-secrets nu vast toe; idempotent en deploy-platform re-applyt ze
# straks gewoon.
log "Apply platform/01-secrets/dev-secrets.yaml (vereist door OM-helm-chart)"
kubectl apply -f "${ROOT}/platform/01-secrets/dev-secrets.yaml" >/dev/null

log "Install OpenMetadata ${OPENMETADATA_VERSION}"
helm upgrade --install openmetadata open-metadata/openmetadata \
  --namespace odap-meta \
  --version "${OPENMETADATA_VERSION}" \
  $(chart_value_args openmetadata) \
  --wait --timeout 15m || warn "OpenMetadata install timing out — continue (init-Job kan later draaien)"

# Sommige OM-chart versies negeren `openmetadata.config.authentication.*`
# vanuit values.yaml (template-pad heeft kleine variaties tussen 1.5.x
# patches). Defensieve helm upgrade --set forceert de publieke URLs zodat
# de Secret die OM gebruikt voor AUTHENTICATION_AUTHORITY / _CALLBACK_URL
# / _PUBLIC_KEYS zeker de juiste hostname bevat — alleen voor cloud-mode.
# Op k3d blijft `*.odap.local` staan; anders krijg je
# "Invalid parameter: redirect_uri" bij login (callback wijst dan naar
# cloud-domein terwijl de browser op .local zit en de Keycloak-client
# alleen *.odap.local accepteert).
if [[ "${IS_CLOUD}" == "yes" ]]; then
  log "Defensieve OM helm-upgrade — pin auth URLs op ${PLATFORM_DOMAIN}"
  helm upgrade --install openmetadata open-metadata/openmetadata \
    --namespace odap-meta \
    --version "${OPENMETADATA_VERSION}" \
    --reuse-values \
    --set openmetadata.config.authentication.authority="https://keycloak.${PLATFORM_DOMAIN}/realms/odap" \
    --set openmetadata.config.authentication.callbackUrl="https://openmetadata.${PLATFORM_DOMAIN}/callback" \
    --set "openmetadata.config.authentication.publicKeys[0]=https://openmetadata.${PLATFORM_DOMAIN}/api/v1/system/config/jwks" \
    --set "openmetadata.config.authentication.publicKeys[1]=https://keycloak.${PLATFORM_DOMAIN}/realms/odap/protocol/openid-connect/certs" \
    --wait --timeout 5m >/dev/null 2>&1 || warn "OM auth-URL pin faalde (helm upgrade) — verifieer manually"
fi

# Chart-bug workaround: OIDC_CUSTOM_PARAMS wordt door templates/secrets.yaml
# als `{{ .customParams | quote | b64enc }}` gerenderd. De `quote`-filter
# wraps `{}` in dubbele quotes → in openmetadata.yaml staat dan
# `customParams: "{}"` (een string), terwijl Java's Jackson een Map verwacht.
# Patch de auth-secret zodat `OIDC_CUSTOM_PARAMS` letterlijk `{}` is, en
# herstart de pod zodat envFrom de nieuwe waarde leest.
log "Patch OIDC_CUSTOM_PARAMS (chart-quote-bug workaround) + restart pod"
PATCH_VAL=$(printf '{}' | base64)
kubectl -n odap-meta patch secret openmetadata-authentication-secret \
  --type='json' \
  -p="[{\"op\":\"replace\",\"path\":\"/data/OIDC_CUSTOM_PARAMS\",\"value\":\"${PATCH_VAL}\"}]" \
  >/dev/null 2>&1 || warn "patch OIDC_CUSTOM_PARAMS faalde — check helm release"
kubectl -n odap-meta delete pod -l app.kubernetes.io/name=openmetadata >/dev/null 2>&1 || true
kubectl -n odap-meta rollout status deploy/openmetadata --timeout=10m >/dev/null \
  || warn "OpenMetadata pod niet ready binnen 10m — check 'kubectl -n odap-meta logs ...'"

# Genereer een admin-JWT op basis van de ingestion-bot in OM's Postgres-DB.
# OM 1.5 met `provider=custom-oidc` heeft geen basic-auth, dus `users/login`
# werkt niet. De `ingestion-bot` user heeft een fernet-encrypted JWT in
# user_entity; we decrypten with the fernet-key from the OM Secret en patchen
# zowel de odap-meta `openmetadata-admin` Secret (init-Job) als een kopie
# in odap-platform (governance_om_ingest DAG draait daar).
log "Genereer admin-JWT (decrypt ingestion-bot fernet-token) + sync naar odap-platform"
# JWT-block fail-soft: als OM nog niet ready is bestaan secret/db niet → skip met warn.
JWT=""
set +e
FERNET=$(kubectl -n odap-meta get secret openmetadata-fernetkey-secret -o jsonpath='{.data}' 2>/dev/null \
  | python3 -c 'import json,sys,base64;d=json.load(sys.stdin);print(next(iter(base64.b64decode(v).decode() for v in d.values())))' 2>/dev/null)
ENCRYPTED=$(kubectl -n odap-data exec postgres-postgresql-0 -c postgresql -- \
  env PGPASSWORD="$(kubectl -n odap-data get secret postgres-postgresql -o jsonpath='{.data.password}' | base64 -d)" \
  psql -U postgres -d openmetadata -t -A -c \
  "SELECT json->'authenticationMechanism'->'config'->>'JWTToken' FROM user_entity WHERE name='ingestion-bot' LIMIT 1;" \
  2>/dev/null | sed 's/^fernet://')
if [[ -n "${FERNET}" && -n "${ENCRYPTED}" ]]; then
  JWT=$(python3 -c "
from cryptography.fernet import MultiFernet, Fernet
mf = MultiFernet([Fernet(k.encode()) for k in '${FERNET}'.split(',')])
print(mf.decrypt(b'${ENCRYPTED}').decode())
" 2>/dev/null)
fi
set -e
if [[ -n "${JWT:-}" ]]; then
  JWT_B64=$(printf '%s' "$JWT" | base64 | tr -d '\n')
  kubectl -n odap-meta patch secret openmetadata-admin --type='json' \
    -p="[{\"op\":\"replace\",\"path\":\"/data/jwtToken\",\"value\":\"${JWT_B64}\"}]" >/dev/null
  # Kopie naar odap-platform — KPO-tasks (governance_om_ingest) draaien daar
  # en lezen `OM_JWT_TOKEN` via secretKeyRef.
  kubectl -n odap-platform create secret generic openmetadata-admin \
    --from-literal=jwtToken="$JWT" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  ok "admin-JWT geseed in odap-meta + odap-platform"
else
  warn "JWT-decrypt faalde — 'kubectl apply -k platform/13-openmetadata-config/' werkt nu niet"
fi

# Kopie van openmetadata-platform-config ConfigMap naar odap-platform — de DAG
# `governance_om_ingest` draait KPO-pods in odap-platform en mountt deze
# ConfigMap op /config voor metadata-ingest workflows.
log "Kopieer openmetadata-platform-config ConfigMap naar odap-platform (voor om-ingest DAG)"
kubectl -n odap-meta get configmap openmetadata-platform-config -o yaml 2>/dev/null \
  | sed -e 's/namespace: odap-meta/namespace: odap/' \
        -e '/resourceVersion:/d' -e '/uid:/d' -e '/creationTimestamp:/d' \
  | kubectl apply -f - >/dev/null \
  || warn "ConfigMap kopie faalde — pas eerst 'kubectl apply -k platform/13-openmetadata-config/' toe"

# Spiegel Keycloak admin-password naar odap-meta zodat de keycloak-om-user-sync
# CronJob er bij kan (cross-NS Secret-mount kan niet in vanilla K8s). Bitnami
# chart stopt het wachtwoord in NS odap-auth, secret `keycloak`, key
# `admin-password`. Wij maken `keycloak-admin-secret` in odap-meta met dezelfde
# data — idempotent via apply.
log "Spiegel Keycloak admin-password naar odap-meta (voor keycloak-om-user-sync CronJob)"
KC_ADMIN_PW=$(kubectl -n odap-auth get secret keycloak -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d)
if [[ -n "${KC_ADMIN_PW:-}" ]]; then
  kubectl -n odap-meta create secret generic keycloak-admin-secret \
    --from-literal=admin-password="${KC_ADMIN_PW}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  ok "keycloak-admin-secret aanwezig in odap-meta"
else
  warn "Keycloak admin-password niet gevonden in odap-auth — keycloak-om-user-sync CronJob zal falen tot dit secret bestaat"
fi

# Spiegel Postgres-root-password naar odap-meta zodat:
#   - openmetadata-init's bot-promote-via-postgres-direct kan connecten
#   - openmetadata-jwt-rotate CronJob de encrypted JWT uit user_entity kan lezen
# Het PG-secret heet `postgres-postgresql` met key `password` in odap-data
# (Bitnami chart default).
log "Spiegel Postgres-password naar odap-meta (voor init-job + jwt-rotate CronJob)"
PG_PW=$(kubectl -n odap-data get secret postgres-postgresql -o jsonpath='{.data.password}' 2>/dev/null | base64 -d)
if [[ -n "${PG_PW:-}" ]]; then
  kubectl -n odap-meta create secret generic postgres-postgresql \
    --from-literal=password="${PG_PW}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  ok "postgres-postgresql aanwezig in odap-meta"
else
  warn "Postgres-password niet gevonden in odap-data — init-job kan ingestion-bot niet tot admin promoten"
fi

# 11. Vector (logs collector → OpenSearch)
log "Install Vector ${VECTOR_VERSION} (Agent-mode op alle nodes)"
helm upgrade --install vector vector/vector \
  --namespace odap-monitoring \
  --version "${VECTOR_VERSION}" \
  $(chart_value_args vector) \
  --wait --timeout 5m \
  || warn "Vector install faalde — log-aggregatie inactief, niet kritisch voor portal."

log "Bootstrap voltooid (mode=${DEPLOYMENT_MODE}, domain=${PLATFORM_DOMAIN})."
echo
if [[ "${IS_LOCAL}" == "yes" ]]; then
  echo "Endpoints (na /etc/hosts injectie + ingress-nginx ready):"
  port_suffix=":${PLATFORM_PORT}"
else
  echo "Endpoints (na public DNS propagation + LoadBalancer ready):"
  port_suffix=""
fi
echo "  https://keycloak.${PLATFORM_DOMAIN}${port_suffix}      (kcadmin / dev-only-pw)"
echo "  https://minio-console.${PLATFORM_DOMAIN}${port_suffix} (platformadmin / dev-only-pw)"
echo "  https://grafana.${PLATFORM_DOMAIN}${port_suffix}       (admin / dev-only-pw)"
echo "  https://openmetadata.${PLATFORM_DOMAIN}${port_suffix}  (admin / dev-only-pw)"
echo
echo "Genereer een OpenMetadata JWT-token (voor init-Job + Airflow DAGs):"
echo "  kubectl -n odap-meta exec deploy/openmetadata -- metadata generate-token > /tmp/om-token"
echo "  kubectl -n odap-meta patch secret openmetadata-admin --type merge \\"
echo "    -p \"{\\\"stringData\\\":{\\\"jwtToken\\\":\\\"\$(cat /tmp/om-token)\\\"}}\""
echo
echo "Volgende stap: make deploy-platform MODE=${DEPLOYMENT_MODE}"
