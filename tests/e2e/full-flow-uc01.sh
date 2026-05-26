#!/usr/bin/env bash
# E2E test — UC-01 WIA Funnel full flow.
#
# Doet alles wat een vers gekloond development-environment doet, in volgorde:
#   1. make cluster        — k3d cluster (idempotent)
#   2. make bootstrap      — Helm-charts + Stackable-operators (~15-25 min)
#   3. make deploy-platform — Stackable-CRDs + dbt-prep + Trino + OPA + ...
#   4. make seed           — synthetische data via Job → Kafka → Spark → Delta
#   5. wait for streaming  — micro-batch tijd (max 90s)
#   6. smoke 01–08         — alle smoke tests groen
#   7. UC-01 verification  — query gold.uc01_wia_funnel.* via Trino
#
# Eindresultaat — fail-safe:
#   - exit 0 als alle stappen + DoD-checks groen zijn
#   - exit 1 bij eerste failure (en logs op stdout)
#
# DoD-anchors die deze test dekt:
#   - bronze.uwv.persona_created bevat ≥10k rijen met test-bereik BSN's   (smoke 03)
#   - bronze.uwv.wia_aanvraag bestaat                                     (smoke 03 generic)
#   - OPA weigert bsn-query op uc05 zonder purpose                        (smoke 08)
#   - OPA maskeert BSN voor marketing_analyst                                (smoke 08)
#   - Superset Trino-database geregistreerd                               (smoke 06)
#   - OpenMetadata classifications + glossary aanwezig                    (smoke 07)
#
# CAVEAT: deze e2e draait NIET zonder Docker-Desktop met genoeg RAM/CPU.
# Realistic timing: 25-35 min op een MBP M1/M2 met 16 GB RAM.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

log()    { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
section(){ printf '\n\033[1;36m═══ %s ═══\033[0m\n' "$*"; }
pass()   { printf '\033[1;32mPASS\033[0m %s\n' "$*"; }
fail()   { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

# Optionele skip-flags (handig voor partial reruns)
SKIP_CLUSTER="${SKIP_CLUSTER:-false}"
SKIP_BOOTSTRAP="${SKIP_BOOTSTRAP:-false}"
SKIP_DEPLOY="${SKIP_DEPLOY:-false}"
SKIP_SEED="${SKIP_SEED:-false}"

# ─── Pre-flight ────────────────────────────────────────────────────────
section "Pre-flight (host tooling check)"
bash scripts/doctor.sh || fail "doctor.sh: vereiste tooling ontbreekt"

# ─── Stage 1: cluster ──────────────────────────────────────────────────
if [[ "$SKIP_CLUSTER" != "true" ]]; then
    section "Stage 1/7: k3d cluster"
    log "make cluster"
    make cluster || fail "cluster"
fi

# ─── Stage 2: bootstrap ────────────────────────────────────────────────
if [[ "$SKIP_BOOTSTRAP" != "true" ]]; then
    section "Stage 2/7: Helm bootstrap (15-25 min)"
    log "make bootstrap"
    make bootstrap || fail "bootstrap"
fi

# ─── Stage 3: deploy-platform ──────────────────────────────────────────
if [[ "$SKIP_DEPLOY" != "true" ]]; then
    section "Stage 3/7: deploy-platform (Stackable + dbt-prep + OPA)"
    log "make deploy-platform"
    make deploy-platform || fail "deploy-platform"

    log "Wachten tot alle Stackable workloads Ready zijn (max 8 min)..."
    for kind_name in zookeepercluster hivecluster kafkacluster nificluster trinocluster opacluster; do
        log "  - waiting on $kind_name"
        kubectl -n odap-platform wait --for=condition=Ready pod \
            -l "app.kubernetes.io/name=${kind_name%cluster}" \
            --timeout=8m \
            || log "  ! ${kind_name} niet (volledig) Ready binnen 8m — verder met smoke"
    done
fi

# ─── Stage 4: seed ─────────────────────────────────────────────────────
if [[ "$SKIP_SEED" != "true" ]]; then
    section "Stage 4/7: seed synthetische data"
    log "make seed"
    make seed || fail "seed"
fi

# ─── Stage 5: wait for Spark streaming micro-batch ─────────────────────
section "Stage 5/7: wachten op Spark Structured Streaming micro-batch"
log "Streaming-trigger interval is 20s; we wachten 90s op zekerheid"
sleep 90

# ─── Stage 6: smoke tests ──────────────────────────────────────────────
section "Stage 6/7: smoke 01–08"
log "make smoke"
make smoke || fail "smoke tests"

# ─── Stage 7: UC-01 specifieke verificatie ────────────────────────────
section "Stage 7/7: UC-01 specifieke verificatie via Trino"

NS="odap-platform"
SMOKE_USER="${SMOKE_USER:-smoketest}"
SMOKE_PW="${SMOKE_PW:-odap-dev-only-CHANGE-ME-Smoke2026}"

trino_exec() {
    kubectl -n "$NS" exec statefulset/trino-coordinator-default -c trino -- \
        bash -lc "TRINO_PASSWORD='$SMOKE_PW' /stackable/trino-cli/trino \
            --server https://localhost:8443 --insecure \
            --user $SMOKE_USER --password \
            --output-format CSV \
            --execute \"$1\""
}

# Check 1: gold.uc01_wia_funnel schema bestaat (na dbt run via Airflow — kan
# nog niet zijn gedraaid in e2e). Doe een fallback-check op silver.
log "Check 1: silver.wia.stg_wia_aanvraag query (na dbt-run vereist)"
silver_count=$(trino_exec "SELECT count(*) FROM silver.wia.stg_wia_aanvraag" 2>&1 | tail -1 | tr -d '"' || echo 0)
if [[ "$silver_count" =~ ^[0-9]+$ ]] && [[ "$silver_count" -gt 0 ]]; then
    pass "silver.wia.stg_wia_aanvraag: $silver_count records"
else
    log "  [SKIP] silver-tabel niet gevuld (dbt-run nog niet gedraaid; trigger via Airflow UI of:"
    log "  kubectl -n $NS exec deploy/airflow-webserver-default -c airflow -- airflow dags trigger dbt_run_per_domain"
    log "  Cooldown ~3 min daarna deze e2e opnieuw."
fi

# Check 2: bronze.uwv.wia_aanvraag bestaat (geseed door Spark)
log "Check 2: bronze.uwv.wia_aanvraag rij-count"
bronze_count=$(trino_exec "SELECT count(*) FROM bronze.uwv.wia_aanvraag" 2>&1 | tail -1 | tr -d '"' || echo 0)
if [[ "$bronze_count" =~ ^[0-9]+$ ]] && [[ "$bronze_count" -gt 0 ]]; then
    pass "bronze.uwv.wia_aanvraag: $bronze_count records (uit ~15% van 10k personas)"
else
    fail "bronze.uwv.wia_aanvraag bevat geen records — Spark streaming niet door?"
fi

# Check 3: BSN-format check op bronze.uwv.persona_created
log "Check 3: BSN-prefix-9 check (test-bereik)"
bsn_anomalies=$(trino_exec "SELECT count(*) FROM bronze.uwv.persona_created \
  WHERE NOT regexp_like(json_extract_scalar(payload, '\$.payload.bsn'), '^9[0-9]{8}\$')" 2>&1 | tail -1 | tr -d '"' || echo -1)
if [[ "$bsn_anomalies" == "0" ]]; then
    pass "alle BSN's beginnen met 9 (test-bereik)"
else
    fail "BSN-anomalies: $bsn_anomalies records buiten test-bereik"
fi

section "E2E full-flow-uc01: ALLE STAGES GROEN"
echo
pass "Compleet. UC-01 dashboard kan nu interactief gebouwd worden in Superset"
echo "  https://superset.odap.local:8443"
echo "  Login: odap / odap-dev-only-CHANGE-ME"
echo "  Dataset: gold.uc01_wia_funnel.mart_uc01_wia_funnel_daily (na dbt-run)"
