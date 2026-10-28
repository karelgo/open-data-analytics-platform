#!/usr/bin/env bash
# Smoke test 08 — OPA-decisions kloppen with the platform policies.
#
set -euo pipefail

NS="${NS:-odap-platform}"

log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }

OPA_URL="http://opa-server.${NS}.svc.cluster.local:8081"

curl_decide() {
  local path="$1"
  local body="$2"
  kubectl -n "$NS" run opa-smoke-$RANDOM \
    --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
    curl -fsS --max-time 10 \
         -H 'Content-Type: application/json' \
         -X POST "${OPA_URL}/v1/data/${path}" \
         -d "$body" 2>/dev/null
}

check() {
  local purpose="$1" catalog="$2" expected="$3"
  local result
  result=$(curl_decide trino/allow "{\"input\":{\"context\":{\"identity\":{\"user\":\"analyst\",\"groups\":[\"claims_analyst\"],\"extraCredentials\":{\"purpose\":\"$purpose\"}}},\"action\":{\"operation\":\"SelectFromColumns\",\"resource\":{\"table\":{\"catalogName\":\"$catalog\",\"schemaName\":\"job_market\",\"tableName\":\"mart_job_inventory\"}}}}}")
  echo "$result" | grep -q "\"result\": *$expected" || fail "Unexpected decision for $catalog/$purpose: $result"
  pass "$catalog / $purpose -> $expected"
}
check labour_market_research gold true
check candidate_screening gold false
check labour_market_research bronze false
pass "Job-market access checks passed"
