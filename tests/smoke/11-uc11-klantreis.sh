#!/usr/bin/env bash
# Smoke test 11 — UC-11 Integrale Customer journey (rego-only).
#
# Valideert dat de UC-11 OPA-rules correct gemodelleerd zijn via `opa test`.
# Geen cluster nodig — de cluster-aware OPA-decision-calls staan in tests/e2e/uc11-flow.sh.
#
# Pre-existing failures in andere tests (zelfs in de smoke 08 baseline) zijn
# een data-path-issue met `data.configmap[...]` resolution in opa-test env;
# die filteren we hier uit en checken alleen UC-11-specifieke tests.
#
# DoD-anchors die deze test dekt:
#   - UC-11 row-filter voor claims_analyst regio + null-safe                 (rego-test)
#   - UC-11 row-filter voor fraud_analyst verbergt medische uitkomst-events    (rego-test)
#   - UC-11 columnMask op event_label voor marketing_analyst                     (rego-test)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
warn() { printf '\033[1;33m  WARN\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }

if ! command -v opa >/dev/null 2>&1; then
  fail "opa CLI niet gevonden — installeer via brew install opa of zie scripts/doctor.sh"
fi

log "Render wrapped test-data (Stackable bundle-pad)"
python3 "$ROOT/scripts/opa-test-data-wrap.py" \
        --dst /tmp/opa-test-data.json >/dev/null \
  || fail "data-wrapper render gefaald"

log "opa test op UC-11 row-filter + column-mask regels"

# opa test exit non-zero bij eventuele fails — bewust niet propageren;
# we filteren hieronder explicit op UC-11 tests.
opa test "$ROOT/opa-policies-src/trino/" \
         /tmp/opa-test-data.json -v \
  > /tmp/opa-test-uc11.log 2>&1 || true

# Alle vier UC-11-specifieke tests moeten slagen met wrapped data.
EXPECTED_PASS=(
  test_uc11_claims_analyst_regio_filter
  test_uc11_fraud_analyst_medical_filter
  test_uc11_event_label_sanitized_for_marketing_analyst
  test_uc11_event_label_visible_for_claims_analyst
)

failed=0
for t in "${EXPECTED_PASS[@]}"; do
  if grep -q "${t}: PASS" /tmp/opa-test-uc11.log; then
    pass "${t}"
  else
    if grep -q "${t}: FAIL" /tmp/opa-test-uc11.log; then
      fail "${t} faalde — zie /tmp/opa-test-uc11.log"
    else
      fail "${t} niet uitgevoerd (test niet gevonden) — zie /tmp/opa-test-uc11.log"
    fi
    failed=$((failed+1))
  fi
done

echo
if [[ "$failed" -eq 0 ]]; then
  pass "smoke 11-uc11-customer-journey: alle UC-11 rego-tests groen"
else
  fail "smoke 11-uc11-customer-journey: $failed UC-11 test(s) gefaald"
fi
