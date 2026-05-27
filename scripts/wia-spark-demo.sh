#!/usr/bin/env bash
# wia-spark-demo.sh — Spark bronze→silver→gold pipeline voor WIA-aanvragen.
#
# Doet wat de Airflow DAG transform_wia_spark.py zou doen, MAAR zonder Airflow.
# Reden: Stackable Airflow 3.0.6 mist het /execution/ API-endpoint (zie
# memory/feedback_stackable_airflow3_execution_api_missing.md). Geen enkele
# DAG kan task-pods registreren tot die infra-bug gefixt is.
#
# Dit script:
#   1. Apply seed-bronze-claims (one-shot SparkApplication, vult bronze)
#   2. Render + apply silver-wia template met unieke RUN_ID
#   3. Render + apply gold-wia template met unieke RUN_ID
#   4. Print Trino-verificatiequery
#
# Elke stap poll `.status.phase` tot Succeeded of Failed. Bij Failed: laat
# de CR staan voor postmortem en exit met error.
#
# Aanroep:
#   make wia-spark-demo               # via Makefile
#   scripts/wia-spark-demo.sh         # direct
#   SKIP_SEED=1 scripts/wia-spark-demo.sh   # gebruik bestaande bronze-data
#
# Vereist: kubectl-context op odap-platform cluster; cluster heeft de
# 08-spark + 11-airflow kustomizations al gedeployed.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NS="odap-platform"
RUN_ID="${RUN_ID:-$(date +%Y%m%d%H%M%S)}"
TIMEOUT_LOOPS="${TIMEOUT_LOOPS:-90}"      # 90 × 10s = 15 min per stap
POLL_INTERVAL=10

log()  { printf "\033[36m[%s] %s\033[0m\n" "$(date +%H:%M:%S)" "$*"; }
ok()   { printf "\033[32m[%s] OK %s\033[0m\n" "$(date +%H:%M:%S)" "$*"; }
fail() { printf "\033[31m[%s] FAIL %s\033[0m\n" "$(date +%H:%M:%S)" "$*"; }

# Wacht tot SparkApplication .status.phase in {Succeeded, Failed}.
wait_for_sparkapp() {
  local name="$1"
  log "Polling SparkApplication/$name (max $((TIMEOUT_LOOPS * POLL_INTERVAL))s)"
  for i in $(seq 1 "$TIMEOUT_LOOPS"); do
    local phase
    phase=$(kubectl -n "$NS" get sparkapplication "$name" \
      -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    printf '  [poll %3d] phase=%s\n' "$i" "$phase"
    case "$phase" in
      Succeeded)
        ok "$name succeeded"
        # Stackable-operator delete'd de driver-pod meteen — cleanup CR ook.
        kubectl -n "$NS" delete sparkapplication "$name" --wait=false \
          >/dev/null 2>&1 || true
        return 0
        ;;
      Failed)
        fail "$name FAILED. Inspect: kubectl describe sparkapplication $name -n $NS"
        # Probeer driver-logs nog te grabben (vaak al weg).
        local drv
        drv=$(kubectl -n "$NS" get pod -o name 2>/dev/null \
          | grep "$name" | grep -- -driver | head -1 || true)
        if [ -n "$drv" ]; then
          echo "--- driver logs (laatste 50) ---"
          kubectl -n "$NS" logs "$drv" --tail=50 2>/dev/null || true
        fi
        return 1
        ;;
    esac
    sleep "$POLL_INTERVAL"
  done
  fail "Timeout na ${TIMEOUT_LOOPS} polls — $name nog niet terminal."
  return 1
}

# Apply een SparkApplication-template met ${RUN_ID}-substitutie.
apply_template() {
  local template="$1"
  log "Apply template $template (RUN_ID=$RUN_ID)"
  sed "s|\${RUN_ID}|$RUN_ID|g" "$template" | kubectl apply -f -
}

# === Stap 1: bronze seed ===
if [ "${SKIP_SEED:-0}" = "1" ]; then
  log "SKIP_SEED=1 — gebruik bestaande bronze.claims.application"
else
  log "=== Stap 1/3: seed-bronze-claims ==="
  kubectl -n "$NS" delete sparkapplication seed-bronze-claims \
    --ignore-not-found >/dev/null
  kubectl apply -f platform/08-spark/apps/seed-bronze-claims.yaml
  wait_for_sparkapp seed-bronze-claims
fi

# === Stap 2: silver ===
log "=== Stap 2/3: silver-wia-$RUN_ID ==="
apply_template platform/11-airflow/jobs/spark-silver-wia.yaml
wait_for_sparkapp "silver-wia-$RUN_ID"

# === Stap 3: gold ===
log "=== Stap 3/3: gold-wia-$RUN_ID ==="
apply_template platform/11-airflow/jobs/spark-gold-wia.yaml
wait_for_sparkapp "gold-wia-$RUN_ID"

# === Klaar ===
ok "Pipeline klaar."
cat <<EOF

Verifieer eindresultaat via Trino:

  kubectl -n $NS exec airflow-scheduler-default-0 -c airflow -- \\
    python3 -c "
  import urllib3, trino
  urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
  cur = trino.dbapi.connect(
      host='trino-coordinator.$NS.svc.cluster.local',
      port=8443, user='smoketest', http_scheme='https', verify=False,
  ).cursor()
  for sql in [
      \"SELECT 'bronze' AS layer, COUNT(*) FROM bronze.claims.application\",
      \"SELECT 'silver-spark', COUNT(*) FROM silver.wia_spark.aanvraag\",
      \"SELECT 'gold-spark', COUNT(*) FROM gold.uc01_wia_spark.funnel_daily\",
  ]:
      cur.execute(sql); print(cur.fetchone())
  "
EOF
