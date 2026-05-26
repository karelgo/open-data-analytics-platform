#!/usr/bin/env bash
# Idempotent post-reset bootstrap for the Multica ↔ watcher loop.
#
# Multica's REST API surface (workspace ids, label ids, user accounts)
# is wiped whenever Postgres is reset or the operator rotates to a new
# email + PAT. The watcher and daemon then file into / claim from a
# workspace that no longer exists, with labels that no longer exist,
# silently. This script re-establishes the contract:
#
#   1. Ensure the target workspace exists (slug from --workspace or
#      MULTICA_WORKSPACE env, default 'platform-ops').
#   2. Seed the standard label set the watcher emits — every label has
#      a stable name + colour so the Multica UI is consistent across
#      resets.
#   3. Patch the watcher's ConfigMap MULTICA_WORKSPACE to point at the
#      chosen slug if it doesn't already.
#   4. Roll the watcher Deployment so the new env takes effect.
#
# Auth precedence:
#   1. --token / -t flag
#   2. MULTICA_API_TOKEN env var
#   3. Secret nanitics-multica-token (key MULTICA_API_TOKEN) in odap-platform
#
# Re-runs are safe — each step is "create if missing".

set -euo pipefail

# ---- shared helpers (logging colours) ----------------------------------
log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

# ---- defaults ----------------------------------------------------------
MULTICA_URL="${MULTICA_URL:-https://multica.odap.local:8443}"
WORKSPACE_SLUG="${MULTICA_WORKSPACE:-platform-ops}"
WORKSPACE_NAME=""   # human-readable; falls back to slug
NAMESPACE="${NAMESPACE:-odap-platform}"
CONFIGMAP_NAME="${CONFIGMAP_NAME:-nanitics-observatory-config}"
DEPLOY_NAME="${DEPLOY_NAME:-nanitics-observatory}"
TOKEN=""
SKIP_ROLLOUT="${SKIP_ROLLOUT:-0}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--workspace SLUG] [--token mul_…] [--skip-rollout] [--help]

Options:
  --workspace, -w SLUG   Multica workspace slug to ensure (default: platform-ops)
  --token, -t TOKEN      Multica PAT (mul_…). Else MULTICA_API_TOKEN env. Else
                         pulled from Secret nanitics-multica-token in $NAMESPACE.
  --skip-rollout         Don't restart the watcher Deployment even if the CM changed.
  --help, -h             Show this help.

Environment overrides:
  MULTICA_URL            default $MULTICA_URL
  MULTICA_WORKSPACE      default workspace slug
  MULTICA_API_TOKEN      fallback for --token
  NAMESPACE              default $NAMESPACE
EOF
}

# ---- arg parsing -------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace|-w) WORKSPACE_SLUG="$2"; shift 2 ;;
    --token|-t)     TOKEN="$2"; shift 2 ;;
    --skip-rollout) SKIP_ROLLOUT=1; shift ;;
    --help|-h)      usage; exit 0 ;;
    *) fail "unknown arg: $1 (try --help)" ;;
  esac
done

[[ -z "$WORKSPACE_NAME" ]] && WORKSPACE_NAME="$WORKSPACE_SLUG"

# ---- 1. resolve token --------------------------------------------------
if [[ -z "$TOKEN" ]]; then
  TOKEN="${MULTICA_API_TOKEN:-}"
fi
if [[ -z "$TOKEN" ]]; then
  log "no --token / MULTICA_API_TOKEN — reading from Secret $NAMESPACE/nanitics-multica-token"
  TOKEN=$(kubectl -n "$NAMESPACE" get secret nanitics-multica-token \
            -o jsonpath='{.data.MULTICA_API_TOKEN}' 2>/dev/null \
          | base64 --decode 2>/dev/null || true)
fi
[[ -z "$TOKEN" ]] && fail "could not obtain a Multica PAT. Provide one via --token, MULTICA_API_TOKEN env, or by provisioning Secret 'nanitics-multica-token' in $NAMESPACE."

# Quick auth sanity-check.
auth_status=$(curl -ksS -o /dev/null -w "%{http_code}" "$MULTICA_URL/api/runtimes?workspace_slug=__nope__" -H "Authorization: Bearer $TOKEN" 2>/dev/null || echo 000)
case "$auth_status" in
  401|403) fail "Multica rejected the PAT (HTTP $auth_status). Mint a fresh token in Settings → API Tokens." ;;
  000)     fail "Multica unreachable at $MULTICA_URL. Check ingress + /etc/hosts." ;;
esac
ok "PAT accepted by Multica (probe returned HTTP $auth_status)."

# ---- 2. ensure workspace ----------------------------------------------
log "ensuring workspace '$WORKSPACE_SLUG' exists"
ws_list=$(curl -ksS "$MULTICA_URL/api/workspaces" -H "Authorization: Bearer $TOKEN")
ws_id=$(printf '%s' "$ws_list" | python3 -c "
import json, sys
slug = sys.argv[1]
for w in json.load(sys.stdin):
    if w.get('slug') == slug:
        print(w.get('id', ''))
        break
" "$WORKSPACE_SLUG")

if [[ -n "$ws_id" ]]; then
  ok "workspace '$WORKSPACE_SLUG' already present (id=$ws_id)"
else
  log "creating workspace '$WORKSPACE_SLUG'"
  payload=$(python3 -c "import json,sys; print(json.dumps({'name':sys.argv[1],'slug':sys.argv[2],'description':'Platform-watcher issue queue. Issues filed automatically by the in-cluster watcher; humans approve, the daemon claims, codex executes.'}))" "$WORKSPACE_NAME" "$WORKSPACE_SLUG")
  ws_id=$(curl -ksS -X POST "$MULTICA_URL/api/workspaces" \
           -H "Authorization: Bearer $TOKEN" \
           -H 'Content-Type: application/json' \
           --data-binary "$payload" \
         | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))")
  [[ -z "$ws_id" ]] && fail "workspace create returned no id (check token's permissions)"
  ok "workspace created (id=$ws_id)"
fi

# ---- 3. seed labels ---------------------------------------------------
log "seeding standard label set in '$WORKSPACE_SLUG'"
existing=$(curl -ksS "$MULTICA_URL/api/labels?workspace_id=$ws_id" \
              -H "Authorization: Bearer $TOKEN" \
            | python3 -c "import json,sys; d=json.load(sys.stdin); print('\n'.join(l['name'] for l in d.get('labels',[])))" 2>/dev/null || echo "")

# Parallel arrays (macOS bash 3.x has no associative arrays). One-string-
# per-pair format keeps it portable. Colours match the seed batch used in
# platform-ops on first deploy.
LABEL_PAIRS=(
  'watcher-filed|#6b7280'
  'approved|#10b981'
  'severity:info|#3b82f6'
  'severity:warning|#f59e0b'
  'severity:critical|#ef4444'
  'area:k8s|#8b5cf6'
  'area:platform|#06b6d4'
  'area:trino|#ec4899'
  'area:spark|#f97316'
  'area:airflow|#84cc16'
  'area:hive|#a78bfa'
)

created=0
for pair in "${LABEL_PAIRS[@]}"; do
  name="${pair%|*}"
  color="${pair##*|}"
  if printf '%s\n' "$existing" | grep -Fxq "$name"; then
    continue
  fi
  payload=$(python3 -c "import json,sys; print(json.dumps({'name':sys.argv[1],'color':sys.argv[2]}))" "$name" "$color")
  resp=$(curl -ksS -X POST "$MULTICA_URL/api/labels?workspace_slug=$WORKSPACE_SLUG" \
           -H "Authorization: Bearer $TOKEN" \
           -H 'Content-Type: application/json' \
           --data-binary "$payload")
  if printf '%s' "$resp" | grep -q '"id"'; then
    created=$((created + 1))
    printf '   + %s\n' "$name"
  else
    warn "label '$name' create failed: $(printf '%s' "$resp" | head -c 160)"
  fi
done
ok "labels: $created new, $(printf '%s\n' "$existing" | grep -c . || true) already present"

# ---- 4. patch watcher ConfigMap (if needed) ---------------------------
current_ws=$(kubectl -n "$NAMESPACE" get cm "$CONFIGMAP_NAME" \
               -o jsonpath='{.data.MULTICA_WORKSPACE}' 2>/dev/null || echo "")
if [[ "$current_ws" == "$WORKSPACE_SLUG" ]]; then
  ok "configmap $CONFIGMAP_NAME already pointed at '$WORKSPACE_SLUG'"
else
  log "patching $CONFIGMAP_NAME: MULTICA_WORKSPACE '${current_ws:-<unset>}' -> '$WORKSPACE_SLUG'"
  kubectl -n "$NAMESPACE" patch cm "$CONFIGMAP_NAME" \
    --type=merge -p "{\"data\":{\"MULTICA_WORKSPACE\":\"$WORKSPACE_SLUG\"}}" >/dev/null
  if [[ "$SKIP_ROLLOUT" -ne 1 ]]; then
    log "rolling deployment/$DEPLOY_NAME to pick up new env"
    kubectl -n "$NAMESPACE" rollout restart deploy/"$DEPLOY_NAME" >/dev/null
    kubectl -n "$NAMESPACE" rollout status deploy/"$DEPLOY_NAME" --timeout=90s >/dev/null
    ok "watcher rolled, now using workspace '$WORKSPACE_SLUG'"
  else
    warn "--skip-rollout: configmap patched but watcher pod still on old env until you restart it"
  fi
fi

ok "multica-bootstrap done — watcher → '$WORKSPACE_SLUG' workspace, ${#LABEL_PAIRS[@]} labels ensured"
