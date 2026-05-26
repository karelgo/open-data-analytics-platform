#!/usr/bin/env bash
# Bootstrap helm charts + Stackable operators on the AKS cluster.
# Thin wrapper around scripts/bootstrap.sh --mode=aks; the mode flag selects
# the values-aks.yaml overlays per chart (managed-csi storage, LoadBalancer
# service, public-domain hostnames).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Force mode=aks regardless of what the caller passed — this script only
# makes sense for AKS.
export DEPLOYMENT_MODE=aks
# shellcheck source=../lib/mode.sh
source "$ROOT/scripts/lib/mode.sh"
parse_mode_args   # picks up DEPLOYMENT_MODE=aks from env
require_context

bash "$ROOT/scripts/bootstrap.sh" --mode=aks

# Postgres reconcile + odap-role + databases nu in bootstrap.sh
# zelf (tussen postgres-install en keycloak-install), zodat Keycloak's
# chart de odap user vindt en niet --atomic-rollback geeft op een
# fresh cluster. Hier alleen de OpenMetadata-mysql-secrets workaround.

# AKS-specific: OpenMetadata's helm chart hardcodes the database-credential
# secret name as 'mysql-secrets' with key 'openmetadata-mysql-password',
# even when the configured driver is postgres. Create it here so
# the openmetadata Deployment can finish init.
log "Create OpenMetadata mysql-secrets (workaround for chart's hardcoded name)"
PG_PW=$(kubectl -n odap-data get secret postgres-postgresql -o jsonpath='{.data.postgres-password}' | base64 -d)
kubectl create namespace odap-meta --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n odap-meta create secret generic mysql-secrets \
  --from-literal=openmetadata-mysql-password="${PG_PW}" \
  --dry-run=client -o yaml | kubectl apply -f -

log "AKS bootstrap done."

# Show LoadBalancer IP so user can update /etc/hosts.
log "Waiting for ingress-nginx LoadBalancer IP..."
for i in $(seq 1 60); do
  LB_IP=$(kubectl -n ingress-nginx get svc ingress-nginx-controller \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  if [[ -n "$LB_IP" ]]; then
    break
  fi
  sleep 5
done

if [[ -n "${LB_IP:-}" ]]; then
  log "Ingress LoadBalancer IP: $LB_IP"
  echo "Add to /etc/hosts:"
  echo "  $LB_IP keycloak.odap.local minio-console.odap.local grafana.odap.local openmetadata.odap.local airflow.odap.local superset.odap.local spark.odap.local"
else
  warn "LoadBalancer IP not yet allocated; run 'kubectl -n ingress-nginx get svc' later."
fi
