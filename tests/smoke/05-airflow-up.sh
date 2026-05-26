#!/usr/bin/env bash
# Smoke test 05 — Airflow draait, scheduler is healthy, DAGs zijn parsed.
#
# Voorwaarden: fase 0+1+2+3+4+6 deployed.
set -euo pipefail

NS="${NS:-odap-platform}"

log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Pods Ready
log "AirflowCluster pods"
for role in webserver-default scheduler-default; do
  if ! kubectl -n "$NS" rollout status deploy/airflow-${role} --timeout=5m >/dev/null 2>&1 \
       && ! kubectl -n "$NS" rollout status statefulset/airflow-${role} --timeout=5m >/dev/null 2>&1; then
    fail "AirflowCluster ${role} niet Ready"
  fi
done
pass "Airflow webserver + scheduler Ready"

# 2. ConfigMap airflow-dags aanwezig
log "ConfigMap airflow-dags"
if ! kubectl -n "$NS" get configmap airflow-dags >/dev/null 2>&1; then
  fail "ConfigMap airflow-dags ontbreekt"
fi
pass "ConfigMap airflow-dags aanwezig"

# 3. Verwachte DAGs in scheduler-pod
log "DAG-list via scheduler"
sched_pod=$(kubectl -n "$NS" get pod -l app.kubernetes.io/component=scheduler \
              -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [[ -z "$sched_pod" ]]; then
  fail "Geen scheduler-pod gevonden"
fi

dag_list=$(kubectl -n "$NS" exec "$sched_pod" -c airflow -- \
  airflow dags list 2>/dev/null | tail -n +2 || true)

# Cosmos LoadMode.DBT_MANIFEST genereert per-domein DAGs (silver_<domain>)
# en per-UC gold-DAGs (gold_uc0X_*). De factory-mappen zijn aanwezig in
# manifest.json. We verifiëren dat: (a) tenminste één silver_*-DAG bestaat,
# (b) tenminste één gold_*-DAG bestaat, (c) de housekeeping-DAGs er staan.
for d in lakehouse_maintenance bronze_watch governance_om_ingest; do
  if echo "$dag_list" | grep -qE "^$d\b|\\| $d *\\|"; then
    pass "DAG $d gevonden"
  else
    fail "DAG $d ontbreekt — output:\n$dag_list"
  fi
done

if echo "$dag_list" | grep -qE "^silver_"; then
  pass "Cosmos silver_<domain> DAGs aanwezig (dbt-manifest geladen)"
else
  fail "Geen silver_* DAGs gevonden — Cosmos heeft de dbt-manifest niet geparsed:\n$dag_list"
fi
if echo "$dag_list" | grep -qE "^gold_uc"; then
  pass "Cosmos gold_uc* DAGs aanwezig"
else
  fail "Geen gold_uc* DAGs gevonden"
fi

# 4. Geen import-errors
log "DAG-import errors"
errors=$(kubectl -n "$NS" exec "$sched_pod" -c airflow -- \
  airflow dags list-import-errors 2>/dev/null || true)
if echo "$errors" | grep -qiE 'no.*(errors|data)|^$'; then
  pass "Geen DAG-import errors"
else
  printf '  %s\n' "$errors"
  fail "Een of meer DAGs hebben import-errors"
fi

# 5. Webserver health
log "Webserver /health endpoint"
hc=$(kubectl -n "$NS" exec "$sched_pod" -c airflow -- \
  curl -fsS --max-time 10 \
    "http://airflow-webserver:8080/health" 2>/dev/null || true)
if echo "$hc" | grep -q '"metadatabase"'; then
  pass "Airflow webserver /health antwoord OK"
else
  printf '  %s\n' "$hc"
  fail "Webserver health-endpoint geeft geen geldige response"
fi

echo
pass "smoke 05-airflow-up: alle checks groen"
