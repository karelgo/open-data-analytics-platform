#!/usr/bin/env bash
# Smoke test 08 — OPA-decisions kloppen met de platform policies.
#
# Runt OPA-decision-calls (in-cluster via curl-pod) tegen een paar key-scenarios:
#
#   1. anonymous user             → allow=false (default-deny)
#   2. crm_medewerker + purpose `klantcontact` op uc05    → allow=true
#   3. data_steward zonder purpose op uc05                → allow=false (DoD)
#   4. crm_medewerker + bsn-column                        → columnMask retourneert masking-expr (DoD)
#   5. wia_beoordelaar + regio AMS op silver.wia          → rowFilter `regio_code = 'AMS'`
#   6. data.steward + diagnose-column (sensitive)         → columnMask = NULL
#
# Vereist: fase 0+1+2+3+9 (OpaCluster + bundle uit fase 9 deployed).
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

# --- 1. Anonymous denied ---------------------------------------------
log "anonymous user op /data/trino/allow"
r=$(curl_decide trino/allow \
    '{"input":{"context":{"identity":{"user":"","groups":[]}},"action":{"operation":"ExecuteQuery"}}}')
echo "$r" | grep -q '"result": *false' \
  && pass "anonymous → allow=false" \
  || fail "anonymous: $r"

# --- 2. crm_medewerker + klantcontact op uc05 → allow ----------------
log "crm_medewerker + klantcontact op gold.uc05_client_360.* → allow=true"
r=$(curl_decide trino/allow \
    '{"input":{"context":{"identity":{"user":"crm.medewerker","groups":["crm_medewerker"],"extraCredentials":{"purpose":"klantcontact"}}},"action":{"operation":"SelectFromColumns","resource":{"table":{"catalogName":"gold","schemaName":"uc05_client_360","tableName":"mart_uc05_client_360"}}}}}')
echo "$r" | grep -q '"result": *true' \
  && pass "crm_medewerker+klantcontact → allow=true" \
  || fail "crm_medewerker+klantcontact: $r"

# --- 3. data_steward zonder purpose op uc05 → deny (DoD!) ------------
log "data_steward ZONDER purpose op gold.uc05 → allow=false (DoD R-AVG-06)"
r=$(curl_decide trino/allow \
    '{"input":{"context":{"identity":{"user":"data.steward","groups":["data_steward"]}},"action":{"operation":"SelectFromColumns","resource":{"table":{"catalogName":"gold","schemaName":"uc05_client_360","tableName":"mart_uc05_client_360"}}}}}')
echo "$r" | grep -q '"result": *false' \
  && pass "data_steward zonder purpose → allow=false (doelbinding-deny)" \
  || fail "data_steward zonder purpose: $r"

# --- 4. crm_medewerker + bsn-kolom → columnMask (DoD!) ---------------
log "crm_medewerker + bsn → columnMask (DoD R-AVG-07)"
r=$(curl_decide trino/columnMask \
    '{"input":{"context":{"identity":{"user":"crm.medewerker","groups":["crm_medewerker"]}},"action":{"operation":"SelectFromColumns","resource":{"column":{"catalogName":"gold","schemaName":"uc05_client_360","tableName":"mart_uc05_client_360","columnName":"bsn"}}}}}')
if echo "$r" | grep -q "concat('XXXXX', substr(bsn, 6, 4))"; then
  pass "BSN gemaskeerd voor crm_medewerker"
else
  fail "BSN-mask onverwacht: $r"
fi

# --- 5. wia_beoordelaar + regio AMS → rowFilter ----------------------
log "wia_beoordelaar (regio=AMS) op silver.wia → rowFilter"
r=$(curl_decide trino/rowFilters \
    '{"input":{"context":{"identity":{"user":"wia.beoordelaar","groups":["wia_beoordelaar"],"extraCredentials":{"regio":"ams"}}},"action":{"operation":"SelectFromColumns","resource":{"table":{"catalogName":"silver","schemaName":"wia","tableName":"aanvraag"}}}}}')
if echo "$r" | grep -q "regio_code = 'AMS'"; then
  pass "row-filter regio_code=AMS toegepast"
else
  fail "row-filter onverwacht: $r"
fi

# --- 6. crm_medewerker + diagnose → NULL-mask ------------------------
log "crm_medewerker + diagnose-column → NULL-mask"
r=$(curl_decide trino/columnMask \
    '{"input":{"context":{"identity":{"user":"crm.medewerker","groups":["crm_medewerker"]}},"action":{"operation":"SelectFromColumns","resource":{"column":{"catalogName":"sensitive","schemaName":"wajong","tableName":"dossier","columnName":"diagnose"}}}}}')
if echo "$r" | grep -q '"expression": *"NULL"'; then
  pass "diagnose gemaskeerd als NULL voor crm_medewerker"
else
  fail "diagnose-mask onverwacht: $r"
fi

echo
pass "smoke 08-opa-decisions: alle DoD-checks groen"
