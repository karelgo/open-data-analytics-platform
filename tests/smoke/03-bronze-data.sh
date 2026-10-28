#!/usr/bin/env bash
# Requires make jobs-run; never reports an absent pipeline as passing.
set -euo pipefail
NS="${NS:-odap-platform}"
HELPER="$(dirname "$0")/_trino_query.py"
count=$(kubectl -n "$NS" exec -i statefulset/trino-coordinator-default -c trino -- \
  env TRINO_USER=smoketest TRINO_SERVER=https://localhost:8443 \
  python3 - 'SELECT count(*) FROM bronze.job_market.observations' < "$HELPER")
[[ "$count" =~ ^[0-9]+$ ]] && [[ "$count" -gt 0 ]] || { echo "No job-market bronze observations; run make jobs-run" >&2; exit 1; }
echo "Bronze contains $count job-market observations"
