#!/usr/bin/env bash
# Build OPA bundle.
#
# Stappen:
#   1. opa fmt --diff   (faal als format off is)
#   2. opa test         (faal bij failing tests)
#   3. Sync rego-files: opa-policies-src/trino/*.rego → platform/10-opa/policies/
#   4. Sync data:       opa-policies-src/data/*.json  → platform/10-opa/policies/
#
# `_test.rego` files worden NIET gesynced — die zijn alleen voor opa test.
#
# Daarna kan `kubectl apply -k platform/10-opa/` de bundle als ConfigMap
# pushen (configMapGenerator.files: list automatisch).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_REGO="$ROOT/opa-policies-src/trino"
SRC_DATA="$ROOT/opa-policies-src/data"
DST_POLICIES="$ROOT/platform/10-opa/policies"

# shellcheck source=lib/log.sh
source "${ROOT}/scripts/lib/log.sh"

# --- 1. opa fmt --diff ------------------------------------------------
if command -v opa >/dev/null 2>&1; then
  log "opa fmt --diff $SRC_REGO/"
  if ! opa fmt --diff "$SRC_REGO/" >/dev/null; then
    warn "opa fmt: er zijn formatting-diffs. Run 'opa fmt -w opa-policies-src/trino/' lokaal."
    opa fmt --diff "$SRC_REGO/" || true
  fi
else
  warn "opa niet geïnstalleerd — fmt + test worden overgeslagen. Installeer voor CI."
fi

# --- 2. opa test ------------------------------------------------------
# Data wordt gewrapped onder data.configmap[<name>][<ns>] zodat `opa test`
# dezelfde paden ziet als de Stackable OpaCluster in productie.
if command -v opa >/dev/null 2>&1; then
  log "Render wrapped test-data → /tmp/opa-test-data.json"
  python3 "$ROOT/scripts/opa-test-data-wrap.py" \
    --src "$SRC_DATA/role_mappings.json" \
    --dst /tmp/opa-test-data.json \
    || fail "Wrapper-render gefaald"

  log "opa test $SRC_REGO/ + /tmp/opa-test-data.json"
  opa test "$SRC_REGO/" /tmp/opa-test-data.json -v \
    || fail "opa test gefaald — fix de tests voor je verder gaat"
fi

# --- 3. Sync rego-files (excl. _test.rego) ---------------------------
log "Sync rego-files naar $DST_POLICIES/"
mkdir -p "$DST_POLICIES"

# Verwijder oude bundle-content (alleen *.rego en *.json — geen recursive rm).
find "$DST_POLICIES" -maxdepth 1 -type f \( -name '*.rego' -o -name 'data.json' \) -delete 2>/dev/null || true

for f in "$SRC_REGO"/*.rego; do
  base="$(basename "$f")"
  if [[ "$base" == *_test.rego ]]; then
    continue
  fi
  cp "$f" "$DST_POLICIES/$base"
  printf "  + %s\n" "$base"
done

# --- 4. Sync data ------------------------------------------------------
# Source-JSON is reeds onder top-level key `role_mappings` gestructureerd
# zodat opa-test (raw load → data.role_mappings.*) en productie-bundle
# (zelfde structuur) consistent zijn. We strippen alleen _-prefixed comments.
log "Sync data → $DST_POLICIES/data.json"
python3 - <<PY
import json
src = "$SRC_DATA/role_mappings.json"
dst = "$DST_POLICIES/data.json"

def strip_underscored(obj):
    if isinstance(obj, dict):
        return {k: strip_underscored(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_underscored(v) for v in obj]
    return obj

with open(src) as f:
    raw = json.load(f)
clean = strip_underscored(raw)
with open(dst, "w") as f:
    json.dump(clean, f, indent=2, sort_keys=True)
print(f"  + data.json ({len(json.dumps(clean))} bytes)")
PY

log "Bundle build klaar. Volgende stap:"
echo "  kubectl apply -k platform/10-opa/"
