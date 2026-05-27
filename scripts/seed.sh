#!/usr/bin/env bash
# Seed — genereer en laad synthetische data via een Kubernetes Job.
#
# Stappen:
#   1. ConfigMaps maken uit data-generation/generators/ en data-generation/*.py
#   2. Job submitten (data-generation/k8s/seed-job.yaml) — schrijft JSONL
#      naar s3a://odap-raw/ (Spark Structured Streaming pikt het op)
#   3. Wachten tot Job complete
#   4. Logs printen voor inspectie
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${NS:-odap-platform}"
COUNT="${COUNT:-10000}"

# shellcheck source=lib/log.sh
source "${ROOT}/scripts/lib/log.sh"

if [[ ! -d "$ROOT/data-generation/generators" ]]; then
  fail "data-generation/generators/ niet gevonden"
fi

command -v kubectl >/dev/null || fail "kubectl niet gevonden"

# MinIO moet bereikbaar zijn for the seed-Job. minio-s3-credentials secret
# is door 01-secrets aangemaakt; de Job mount die rechtstreeks.
log "Wacht tot MinIO bereikbaar is (max 5 min)"
for _ in {1..30}; do
  eps=$(kubectl -n "$NS" get endpoints minio \
          -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null || true)
  [[ -n "$eps" ]] && break
  sleep 10
done
[[ -z "${eps:-}" ]] && warn "minio service zonder endpoints — seed kan falen."

log "ConfigMap data-generation-generators (uit data-generation/generators/)"
kubectl -n "$NS" create configmap data-generation-generators \
  --from-file="$ROOT/data-generation/generators/" \
  --dry-run=client -o yaml | kubectl apply -f -

log "ConfigMap data-generation-scripts (load_to_s3.py + load_to_minio_staging.py)"
kubectl -n "$NS" create configmap data-generation-scripts \
  --from-file=load_to_s3.py="$ROOT/data-generation/load_to_s3.py" \
  --from-file=load_to_minio_staging.py="$ROOT/data-generation/load_to_minio_staging.py" \
  --dry-run=client -o yaml | kubectl apply -f -

log "Verwijder eventueel bestaande seed-Job"
kubectl -n "$NS" delete job seed-data-generation --ignore-not-found

log "Apply seed Job (count=${COUNT})"
# COUNT en SEED zijn in de Job-yaml hardcoded op 10000/2026. Voor variatie:
# kustomize patch of een alternative manifest.
kubectl apply -f "$ROOT/data-generation/k8s/seed-job.yaml"

log "Wacht op Job completion (max 10 min)"
if ! kubectl -n "$NS" wait --for=condition=complete --timeout=10m \
       job/seed-data-generation; then
  warn "Job is niet binnen 10 min Complete; print logs:"
  kubectl -n "$NS" logs job/seed-data-generation --tail=200 || true
  fail "seed-Job niet succesvol"
fi

log "Job-logs:"
kubectl -n "$NS" logs job/seed-data-generation --tail=50

log "Klaar. Spark file-streaming-job pikt JSONL-files uit s3a://odap-raw/ op (kan 1-2 min duren voor batch verschijnt)."
