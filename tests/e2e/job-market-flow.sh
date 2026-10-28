#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
bash scripts/job-market-cluster.sh
bash tests/smoke/03-bronze-data.sh
HELPER=tests/smoke/_trino_query.py
NS="${NS:-odap-platform}"
count=$(kubectl -n "$NS" exec -i statefulset/trino-coordinator-default -c trino -- \
  env TRINO_USER=smoketest TRINO_SERVER=https://localhost:8443 \
  python3 - 'SELECT count(*) FROM gold.job_market.mart_job_inventory' < "$HELPER")
[[ "$count" =~ ^[0-9]+$ ]] && [[ "$count" -gt 0 ]] || { echo "Job inventory is empty" >&2; exit 1; }
echo "Gold inventory contains $count jobs after the tested pipeline"
