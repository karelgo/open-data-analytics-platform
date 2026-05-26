#!/usr/bin/env bash
# Run de OpenMetadata demo-seed Job: synthetiseert UC-mart tabel-entities +
# verrijking voor UCs die nog niet door dbt zijn gematerialiseerd.
#
# Zie platform/13-openmetadata-config/demo-synth-marts-job.yaml voor
# achtergrond + lijst van marts.
#
# Idempotent — re-runs slaan bestaande tabellen over. Veilig om na elke
# cluster-reset uit te voeren, en harmless als dbt-build inmiddels echte
# tabellen heeft aangelegd (PATCH-based verrijking blijft behouden).
#
# Trigger:
#   make om-demo-seed
#   OF: bash scripts/om-demo-seed.sh
#
# Pre-conditions:
#   - openmetadata-init Job heeft gedraaid (teams + domains + dataProducts
#     + custom-property types geseed).
#   - Trino-catalog ingest heeft de bronze/gold schemas onder trino
#     aangelegd.

set -euo pipefail

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

NAMESPACE="${NAMESPACE:-odap-meta}"
JOB_NAME="om-demo-seed"
MANIFEST="${MANIFEST:-platform/13-openmetadata-config/demo-synth-marts-job.yaml}"
TIMEOUT="${TIMEOUT:-300s}"

# Werk relatief vanaf repo-root (zelfde plek als waar de Makefile staat).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

[[ -f "$MANIFEST" ]] || fail "manifest niet gevonden: $MANIFEST"

if ! kubectl -n "$NAMESPACE" get secret openmetadata-admin >/dev/null 2>&1; then
  fail "secret openmetadata-admin ontbreekt in namespace $NAMESPACE — eerst 'make deploy' draaien."
fi

# Wacht expliciet op openmetadata-init zodat teams/domains/dataProducts/
# customProperties bestaan voordat de synth-Job ze probeert te koppelen.
# Init-Job heeft TTL 3600s; als die al opgeruimd is, gewoon doorgaan.
if kubectl -n "$NAMESPACE" get job openmetadata-init >/dev/null 2>&1; then
  log "Wachten tot openmetadata-init Job Complete is"
  kubectl -n "$NAMESPACE" wait --for=condition=Complete --timeout=300s job/openmetadata-init 2>/dev/null \
    || warn "openmetadata-init niet binnen 5 min klaar — synth kan falen op missende refs"
fi

log "Cleanup eventuele eerdere Job-run"
kubectl -n "$NAMESPACE" delete job "$JOB_NAME" --ignore-not-found >/dev/null

log "Apply Job-manifest: $MANIFEST"
kubectl apply -f "$MANIFEST" >/dev/null

log "Wachten tot Job klaar is (timeout=$TIMEOUT)"
if ! kubectl -n "$NAMESPACE" wait --for=condition=Complete --timeout="$TIMEOUT" "job/$JOB_NAME" 2>/dev/null; then
  warn "Job is niet binnen $TIMEOUT klaar — logs hieronder."
  kubectl -n "$NAMESPACE" logs "job/$JOB_NAME" --tail=80 || true
  fail "om-demo-seed Job timed out / failed."
fi

# Filter pip-warnings; toon alleen synth-uitvoer.
kubectl -n "$NAMESPACE" logs "job/$JOB_NAME" --tail=200 2>/dev/null \
  | grep -vE '^WARNING|^ *$' || true

ok "om-demo-seed klaar — UC-marts verrijkt in OpenMetadata."
