#!/usr/bin/env bash
# Fast e2e — alleen smoke 01-08 + UC-01 verify (improvements #14).
#
# Gebruikt voor PR-CI: vermijdt de 15-25 min van bootstrap door aan te nemen
# dat het cluster al draait (met fase 0-9 deployed).
#
# Voor een full from-scratch e2e: tests/e2e/full-flow-uc01.sh
#
# Verwachte runtime: 3-5 min.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

log()    { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
section(){ printf '\n\033[1;36m═══ %s ═══\033[0m\n' "$*"; }
pass()   { printf '\033[1;32mPASS\033[0m %s\n' "$*"; }
fail()   { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

# ─── Pre-checks ─────────────────────────────────────────────────────────
section "Pre-checks (cluster reachability)"

kubectl cluster-info >/dev/null 2>&1 \
  || fail "geen kubectl-context — run 'make cluster && make bootstrap && make deploy-platform' eerst"

if ! kubectl get ns odap-platform >/dev/null 2>&1; then
    fail "namespace odap-platform ontbreekt — bootstrap niet gedraaid?"
fi

# ─── Stage 1: smoke 01-08 ───────────────────────────────────────────────
section "Stage 1/2: smoke tests (01-08)"
make smoke || fail "smoke tests"

# ─── Stage 2: UC-01 quick verify ────────────────────────────────────────
section "Stage 2/2: UC-01 quick verify (BSN + bronze rij-count)"

NS="odap-platform"
SMOKE_PW="${SMOKE_PW:-odap-dev-only-CHANGE-ME-Smoke2026}"

trino_exec() {
    kubectl -n "$NS" exec statefulset/trino-coordinator-default -c trino -- \
        bash -lc "TRINO_PASSWORD='$SMOKE_PW' /stackable/trino-cli/trino \
            --server https://localhost:8443 --insecure \
            --user smoketest --password \
            --output-format CSV \
            --execute \"$1\""
}

bronze_count=$(trino_exec "SELECT count(*) FROM bronze.persons.created" 2>&1 \
                  | tail -1 | tr -d '"' || echo 0)

if [[ "$bronze_count" =~ ^[0-9]+$ ]] && [[ "$bronze_count" -gt 0 ]]; then
    pass "bronze.persons.created: $bronze_count records"
else
    fail "geen records in bronze.persons.created"
fi

bsn_anomalies=$(trino_exec "SELECT count(*) FROM bronze.persons.created \
  WHERE NOT regexp_like(json_extract_scalar(payload, '\$.payload.bsn'), '^9[0-9]{8}\$')" 2>&1 \
                  | tail -1 | tr -d '"' || echo -1)
[[ "$bsn_anomalies" == "0" ]] \
  && pass "BSN-prefix-9 hold (0 anomalies)" \
  || fail "BSN-anomalies: $bsn_anomalies"

section "Fast-e2e: GROEN (runtime $(($SECONDS / 60))m$(($SECONDS % 60))s)"
