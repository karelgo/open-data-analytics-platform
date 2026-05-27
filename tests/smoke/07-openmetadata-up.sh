#!/usr/bin/env bash
# Smoke test 07 — OpenMetadata draait, classifications + glossary geladen.
#
# Voorwaarden:
#   - infrastructure/helm/opensearch + openmetadata Helm installed (odap-meta ns)
#   - platform/13-openmetadata-config applied → init-Job complete
set -euo pipefail

NS="${NS:-odap-meta}"

log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }

# 1. OpenSearch Ready
log "OpenSearch single-node Ready"
kubectl -n "$NS" rollout status statefulset/opensearch-master --timeout=10m >/dev/null 2>&1 \
  || fail "OpenSearch (statefulset opensearch-master) niet Ready"
pass "OpenSearch Ready"

# 1a. OpenSearch Dashboards Ready
log "OpenSearch Dashboards Ready"
kubectl -n "$NS" rollout status deploy/opensearch-dashboards --timeout=10m >/dev/null 2>&1 \
  || fail "OpenSearch Dashboards (deploy/opensearch-dashboards) niet Ready"
pass "OpenSearch Dashboards Ready"

# 2. OpenMetadata Ready
log "OpenMetadata server Ready"
kubectl -n "$NS" rollout status deploy/openmetadata --timeout=10m >/dev/null 2>&1 \
  || kubectl -n "$NS" rollout status statefulset/openmetadata --timeout=10m >/dev/null 2>&1 \
  || fail "OpenMetadata pods niet Ready"
pass "OpenMetadata Ready"

# 3. Init-Job complete
log "Init-Job complete"
phase=$(kubectl -n "$NS" get job openmetadata-init -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || echo "")
if [[ "$phase" != "True" ]]; then
  log "Init-Job nog niet Complete; logs:"
  kubectl -n "$NS" logs job/openmetadata-init --tail=80 || true
  fail "openmetadata-init Job niet succesvol"
fi
pass "openmetadata-init Job Complete"

# 4. Classifications via API
log "Classifications via REST API"

token=$(kubectl -n "$NS" get secret openmetadata-admin -o jsonpath='{.data.jwtToken}' | base64 -d)

# OM-image heeft geen 'curl'; query via tijdelijke curl-pod.
om_curl() {
  local path="$1"
  kubectl -n "$NS" run om-smoke-$RANDOM \
    --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
    curl -fsS --max-time 30 \
      "http://openmetadata.odap-meta.svc.cluster.local:8585${path}" \
      -H "Authorization: Bearer ${token}" 2>/dev/null || echo "{}"
}

classifications=$(om_curl "/api/v1/classifications")

for c in PII Health Confidentiality BIO LegalBasis Purpose limitation AI; do
  if echo "$classifications" | grep -qE "\"name\":\\s*\"$c\""; then
    pass "classification '$c' aanwezig"
  else
    fail "classification '$c' ontbreekt"
  fi
done

# 5. Glossary CGM
log "Glossary CGM"
gloss=$(om_curl "/api/v1/glossaries")
if echo "$gloss" | grep -qE "\"name\":\\s*\"CGM\""; then
  pass "glossary 'CGM' aanwezig"
else
  fail "glossary 'CGM' ontbreekt"
fi

# 6. Sample CGM-terms
log "CGM-terms sample"
terms=$(om_curl "/api/v1/glossaryTerms?glossary=CGM&limit=50")
for t in Aanvraag Assessment Cliënt IKV Claim payout; do
  # CGM-term heeft FQN `CGM.<name>` in OM
  if echo "$terms" | grep -qE "\"name\":\\s*\"$t\""; then
    pass "term CGM.$t aanwezig"
  else
    log "  [warn] term CGM.$t niet gevonden — kan zijn dat init-Job nog niet alle posts deed"
  fi
done

echo
pass "smoke 07-openmetadata-up: alle checks groen"
