#!/usr/bin/env bash
# Idempotent setup van de OpenMetadata EventSubscription die taskResolved-
# events naar de om-access-bridge stuurt.
#
# Achtergrond: subscriptions zitten in OM's database, niet in de
# ConfigMap/init-Job. Bij een platform-reset zijn ze weg. Dit script
# herstelt 'm vanuit een POST naar /api/v1/events/subscriptions.
#
# Idempotent: bestaande subscription → exit 0 zonder wijzigingen.

set -euo pipefail

NS="${OM_NS:-odap-meta}"
SUB_NAME="om-access-bridge"
BRIDGE_URL="${OM_BRIDGE_WEBHOOK_URL:-http://om-access-bridge.odap-platform.svc.cluster.local/webhooks/om}"
WEBHOOK_SECRET="${OM_WEBHOOK_SECRET:-odap-dev-only-CHANGE-ME-om-webhook-secret}"
PF_PORT="${PF_PORT:-18585}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

PF_PID=
cleanup() { [ -n "$PF_PID" ] && kill $PF_PID 2>/dev/null || true; }
trap cleanup EXIT

log "Port-forward openmetadata → 127.0.0.1:${PF_PORT}"
kubectl -n "$NS" port-forward svc/openmetadata ${PF_PORT}:8585 >/tmp/om-pf.log 2>&1 &
PF_PID=$!
for i in 1 2 3 4 5 6 7 8 9 10; do
  curl -fsS --max-time 2 "http://127.0.0.1:${PF_PORT}/api/v1/system/version" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS --max-time 5 "http://127.0.0.1:${PF_PORT}/api/v1/system/version" >/dev/null 2>&1 \
  || fail "OM port-forward niet bereikbaar — $(tail -3 /tmp/om-pf.log)"

TOKEN=$(kubectl -n "$NS" get secret openmetadata-admin -o jsonpath='{.data.jwtToken}' | base64 -d)
[ -n "$TOKEN" ] || fail "openmetadata-admin secret heeft geen jwtToken"

OM="http://127.0.0.1:${PF_PORT}"
A="Authorization: Bearer $TOKEN"

log "EventSubscription ${SUB_NAME} aanwezig?"
EXISTS=$(curl -sS -o /tmp/sub.json -w '%{http_code}' -H "$A" "$OM/api/v1/events/subscriptions/name/${SUB_NAME}" || echo "000")
if [ "$EXISTS" = "200" ]; then
  pass "subscription al aanwezig — geen wijziging"
  exit 0
fi

log "POST nieuwe subscription"
cat > /tmp/sub-body.json <<EOF
{
  "name": "${SUB_NAME}",
  "displayName": "OM Access Bridge (ADR-0008)",
  "alertType": "Notification",
  "resources": ["task"],
  "destinations": [
    {
      "category": "External",
      "type": "Webhook",
      "config": {
        "endpoint": "${BRIDGE_URL}",
        "secretKey": "${WEBHOOK_SECRET}"
      }
    }
  ],
  "enabled": true
}
EOF

STATUS=$(curl -sS -o /tmp/sub-resp.json -w '%{http_code}' -X POST -H "$A" -H 'Content-Type: application/json' \
  "$OM/api/v1/events/subscriptions" -d @/tmp/sub-body.json)
[ "$STATUS" = "201" ] || fail "subscription POST=$STATUS body=$(cat /tmp/sub-resp.json | head -c 300)"
pass "subscription aangemaakt en enabled"
