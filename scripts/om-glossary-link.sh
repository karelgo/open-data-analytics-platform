#!/usr/bin/env bash
# Koppel CGM-glossary-termen aan de tabellen waar ze logisch bij horen.
#
# Vult de gaten die de standaard enrichment laat liggen: termen die niet
# in de dbt `cgm_entiteiten`-meta staan (Customer journey, EventStream, Fase,
# Persona, Werknemer, Werkgever, Dienstverband, Ontslag, Diagnose,
# Inkomen, Huishouden, Aggregaat, Uitkomst) krijgen alsnog koppeling aan
# de bronze stg_*- en relevante mart-tabellen.
#
# Zie platform/13-openmetadata-config/glossary-link-job.yaml voor de
# mapping (CGM-term → (schema, table)-paren).
#
# Idempotent — bestaande tags blijven staan, alleen ontbrekende worden
# toegevoegd.
#
# Trigger:
#   make om-glossary-link
#   OF: bash scripts/om-glossary-link.sh
#
# Pre-conditions:
#   - openmetadata-init heeft CGM-glossary geseed.
#   - Tabellen bestaan in OM (Trino-catalog-ingest + evt. 'make om-demo-seed').

set -euo pipefail

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

NAMESPACE="${NAMESPACE:-odap-meta}"
JOB_NAME="om-glossary-link"
MANIFEST="${MANIFEST:-platform/13-openmetadata-config/glossary-link-job.yaml}"
TIMEOUT="${TIMEOUT:-300s}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

[[ -f "$MANIFEST" ]] || fail "manifest niet gevonden: $MANIFEST"

if ! kubectl -n "$NAMESPACE" get secret openmetadata-admin >/dev/null 2>&1; then
  fail "secret openmetadata-admin ontbreekt in namespace $NAMESPACE — eerst 'make deploy' draaien."
fi

# Wacht op openmetadata-init (seedt de CGM-glossary). Init-Job heeft TTL
# 3600s; als die al opgeruimd is, gewoon doorgaan.
if kubectl -n "$NAMESPACE" get job openmetadata-init >/dev/null 2>&1; then
  log "Wachten tot openmetadata-init Job Complete is"
  kubectl -n "$NAMESPACE" wait --for=condition=Complete --timeout=300s job/openmetadata-init 2>/dev/null \
    || warn "openmetadata-init niet binnen 5 min klaar — koppeling kan falen op missende CGM-termen"
fi

log "Cleanup eventuele eerdere Job-run"
kubectl -n "$NAMESPACE" delete job "$JOB_NAME" --ignore-not-found >/dev/null

log "Apply Job-manifest: $MANIFEST"
kubectl apply -f "$MANIFEST" >/dev/null

log "Wachten tot Job klaar is (timeout=$TIMEOUT)"
if ! kubectl -n "$NAMESPACE" wait --for=condition=Complete --timeout="$TIMEOUT" "job/$JOB_NAME" 2>/dev/null; then
  warn "Job is niet binnen $TIMEOUT klaar — logs hieronder."
  kubectl -n "$NAMESPACE" logs "job/$JOB_NAME" --tail=80 || true
  fail "om-glossary-link Job timed out / failed."
fi

kubectl -n "$NAMESPACE" logs "job/$JOB_NAME" --tail=200 2>/dev/null \
  | grep -vE '^WARNING|^ *$' || true

ok "om-glossary-link klaar — CGM-termen gekoppeld aan tables."
