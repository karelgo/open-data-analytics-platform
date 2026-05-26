#!/usr/bin/env bash
# scripts/alert-test.sh — verifieer end-to-end-alert-bezorging.
#
# Stuurt een synthetische alert direct naar Alertmanager via amtool of
# kubectl-exec-curl. Daarna kun je 'm verifiëren:
#   - in k3d : open https://mailhog.odap.local:8443/  (MailHog UI)
#   - in aks : check de inbox van platform-alerts@example.com
#
# Gebruik:
#   bash scripts/alert-test.sh              # default: 1 warning
#   bash scripts/alert-test.sh critical     # critical-severity
#   bash scripts/alert-test.sh resolve      # verstuur dezelfde alert
#                                           # als 'resolved'
#
# Vereisten:
#   - kubectl context wijst naar de cluster waar Alertmanager draait
#   - Alertmanager runt in namespace odap-monitoring
#
# Exit-codes: 0 = success, !=0 = failure.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/mode.sh
source "${ROOT}/scripts/lib/mode.sh"
parse_mode_args "$@"
# parse_mode_args slokt --mode op. Positionele args staan in REMAINING_ARGS.

ACTION="${REMAINING_ARGS[0]:-warning}"
NS="odap-monitoring"
AM_SVC="prometheus-kube-prometheus-alertmanager"
AM_PORT="9093"

if ! kubectl -n "${NS}" get svc "${AM_SVC}" >/dev/null 2>&1; then
  error "Alertmanager-service ${AM_SVC} niet gevonden in ${NS}. Is alertmanager.enabled: true in values-${DEPLOYMENT_MODE}.yaml?"
fi

# Timestamp in RFC3339 (UTC).
now() { date -u +%Y-%m-%dT%H:%M:%S.000Z; }
future() { date -u -v+5M +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null \
           || date -u -d '+5 minutes' +%Y-%m-%dT%H:%M:%S.000Z; }

case "$ACTION" in
  critical) SEV="critical" ;;
  warning)  SEV="warning"  ;;
  resolve)  SEV="warning"  ;;
  *)        error "Ongeldig action='${ACTION}'. Verwacht: warning | critical | resolve." ;;
esac

if [[ "$ACTION" == "resolve" ]]; then
  # endsAt in het verleden → Alertmanager markeert resolved.
  STARTS_AT="$(date -u -v-10M +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null \
              || date -u -d '-10 minutes' +%Y-%m-%dT%H:%M:%S.000Z)"
  ENDS_AT="$(date -u -v-1M +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null \
            || date -u -d '-1 minute' +%Y-%m-%dT%H:%M:%S.000Z)"
else
  STARTS_AT="$(now)"
  ENDS_AT="$(future)"
fi

PAYLOAD=$(cat <<JSON
[{
  "labels": {
    "alertname": "SyntheticTestAlert",
    "severity": "${SEV}",
    "component": "alert-test",
    "namespace": "${NS}",
    "service": "scripts/alert-test.sh"
  },
  "annotations": {
    "summary": "Synthetische alert — end-to-end-test (severity=${SEV}, action=${ACTION})",
    "description": "Verstuurd door scripts/alert-test.sh om de Alertmanager→email pipeline te valideren. Verwijderbaar; geen actie nodig.",
    "runbook_url": "/docs/runbook.md#97-alert-pipeline-end-to-end-test"
  },
  "startsAt": "${STARTS_AT}",
  "endsAt": "${ENDS_AT}",
  "generatorURL": "https://alertmanager.odap.local/alert-test"
}]
JSON
)

log "Verstuur synthetische alert (severity=${SEV}, action=${ACTION}) naar ${AM_SVC}:${AM_PORT}"

# Port-forward in de achtergrond zodat we niet via amtool hoeven (vereist
# extra install). Op CI / locals werkt port-forward + curl.
PF_PORT=19093
PF_PID=""
trap '[[ -n "${PF_PID}" ]] && kill "${PF_PID}" 2>/dev/null || true' EXIT

kubectl -n "${NS}" port-forward "svc/${AM_SVC}" ${PF_PORT}:${AM_PORT} \
  >/dev/null 2>&1 &
PF_PID=$!

# Wacht tot port-forward klaar is (max 5s).
for _ in $(seq 1 10); do
  if curl -sf "http://127.0.0.1:${PF_PORT}/-/healthy" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -sf "http://127.0.0.1:${PF_PORT}/-/healthy" >/dev/null 2>&1; then
  error "port-forward naar Alertmanager mislukt. Check 'kubectl -n ${NS} get pods'."
fi

RESP="$(curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -d "${PAYLOAD}" \
  "http://127.0.0.1:${PF_PORT}/api/v2/alerts" \
  -o /tmp/alert-test-response.json \
  -w '%{http_code}')" || true

if [[ "${RESP}" != "200" && "${RESP}" != "202" ]]; then
  warn "Alertmanager-respons: HTTP ${RESP}"
  cat /tmp/alert-test-response.json
  exit 1
fi

ok "Alert verstuurd (HTTP ${RESP})."

case "$DEPLOYMENT_MODE" in
  k3d)
    echo
    echo "Verifieer: open MailHog UI → https://mailhog.odap.local:8443/"
    echo "           (of port-forward: kubectl -n ${NS} port-forward svc/mailhog 8025:8025)"
    echo "Verwacht: nieuwe mail met subject '[FIRING:1] SyntheticTestAlert (${SEV})'"
    ;;
  aks)
    echo
    echo "Verifieer: check de inbox van platform-alerts@example.com"
    echo "          (smarthost via platform-overlays/aks/14-monitoring/alertmanager-smtp-prod.yaml)"
    ;;
esac

if [[ "$ACTION" != "resolve" ]]; then
  echo
  echo "Tip: na bevestiging, draai 'bash scripts/alert-test.sh resolve' om de alert te resolven."
fi
