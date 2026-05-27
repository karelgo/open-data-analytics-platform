#!/usr/bin/env bash
# One-shot deploy of the full AKS environment:
#  1. terraform apply (AKS + certs)                                ~10-15 min
#  2. fetch kubeconfig
#  3. bootstrap helm charts + Stackable operators                  ~15-20 min
#  4. apply platform manifests + AKS post-deploy hooks             ~10-15 min
#  5. summarise endpoints
#
# Idempotent: re-run anytime; terraform/helm see no-op when nothing changed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

log()   { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
error() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

[[ -f scripts/azure/env.sh ]] || error "scripts/azure/env.sh ontbreekt — kopieer scripts/azure/env.sh.example en vul de SP-secret in."
# shellcheck source=/dev/null
source scripts/azure/env.sh
[[ -n "${ARM_CLIENT_SECRET:-}" && -n "${TF_VAR_sp_client_secret:-}" ]] \
  || error "ARM_CLIENT_SECRET / TF_VAR_sp_client_secret niet gezet (zie scripts/azure/env.sh)."

log "Step 1/4: terraform apply (AKS + certs, ~10-15 min)"
bash scripts/azure/aks-up.sh

log "Step 2/4: fetch kubeconfig"
bash scripts/azure/aks-context.sh

log "Step 3/4: bootstrap helm charts + Stackable operators"
bash scripts/azure/aks-bootstrap.sh

log "Step 4/4: deploy platform manifests"
bash scripts/azure/aks-deploy.sh

log "Smoke tests (best-effort)"
bash scripts/run-smoke-tests.sh || warn "Niet alle smoke tests groen — zie tests/smoke output. Platform is meestal nog steeds bruikbaar."

# ---- Summarise endpoints ----
echo
log "Endpoints"
LB_PUBLIC=$(kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
LB_INTERNAL=$(kubectl -n ingress-nginx get svc ingress-nginx-controller-internal -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
echo "  Public ingress LB IP   : ${LB_PUBLIC:-<not allocated>}"
echo "  Internal ingress LB IP : ${LB_INTERNAL:-<not allocated>}"
echo

log "Done. Stop the cluster when idle:  make aks-stop-all   (full teardown: make aks-down-all)"
