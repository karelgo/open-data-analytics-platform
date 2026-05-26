#!/usr/bin/env bash
# Bootstrap helm charts + Stackable operators on the StackIT SKE cluster.
# Thin wrapper around scripts/bootstrap.sh --mode=stackit; the mode flag selects
# the values-stackit.yaml overlays per chart (premium-perf*-stackit storage,
# LoadBalancer service pinned to the reserved Floating IP, example.com
# hostnames).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Force mode=stackit regardless of what the caller passed.
export DEPLOYMENT_MODE=stackit
# shellcheck source=../lib/mode.sh
source "$ROOT/scripts/lib/mode.sh"
parse_mode_args
require_context

bash "$ROOT/scripts/bootstrap.sh" --mode=stackit

# Postgres reconcile + odap-role + databases nu in bootstrap.sh
# zelf (tussen postgres-install en keycloak-install), zodat Keycloak's
# chart de odap user vindt en niet --atomic-rollback geeft op een
# fresh cluster. Hier alleen de OpenMetadata-mysql-secrets workaround.

# Same OpenMetadata mysql-secrets workaround as AKS — the chart hardcodes that
# secret name even when running on postgres.
log "Create OpenMetadata mysql-secrets (workaround for chart's hardcoded name)"
kubectl create namespace odap-meta --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n odap-meta create secret generic mysql-secrets \
  --from-literal=openmetadata-mysql-password="${PG_PW}" \
  --dry-run=client -o yaml | kubectl apply -f -

log "StackIT bootstrap done."

# Show LoadBalancer IP — should match the reserved Floating IP 188.34.84.39.
# If it doesn't, the values-stackit.yaml loadBalancerIP setting is wrong.
log "Waiting for ingress-nginx LoadBalancer IP..."
EXPECTED_IP="188.34.84.39"
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
  if [[ "$LB_IP" != "$EXPECTED_IP" ]]; then
    warn "Ingress IP ($LB_IP) does NOT match reserved Floating IP ($EXPECTED_IP)."
    warn "Fix infrastructure/helm/ingress-nginx/values-stackit.yaml: loadBalancerIP must equal the reserved IP."
  else
    ok "Ingress IP matches reserved Floating IP — DNS records for *.example.com should resolve."
  fi
else
  warn "LoadBalancer IP not yet allocated; run 'kubectl -n ingress-nginx get svc' later."
fi
