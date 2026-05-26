#!/usr/bin/env bash
# Fix OpenMetadata 1.12 OpenSearch-index-mapping bug.
#
# OM 1.12 index-templates markeren `glossaryTags`, `classificationTags`,
# `deleted` en `entityStatus` als plain `text`, maar OM's eigen
# search-queries aggregeren erop alsof het `keyword` zijn. Resultaat:
# elke search-call retourneert 500 "Text fields are not optimised for
# operations that require per-document field data".
#
# Symptoom: OM UI Explore-pagina is leeg ondanks dat Postgres tables
# heeft. /api/v1/search/query?q=* → 500.
#
# Workaround: `fielddata=true` op die 4 velden via PUT _mapping. Geen
# index-rebuild nodig — change is online, kost wat heap-RAM op OS.
#
# Idempotent. Past op alle OM entity-indices (table/dashboard/pipeline/
# glossary_term/database/database_schema/data_product/domain/user/team/
# topic/container/dashboard_data_model/mlmodel/*_service_search_index).
#
# Tijdelijk — bij volgende OM-versie of OS-index-template-update zou de
# upstream fix de workaround moeten vervangen. Tot dan: run dit na elke
# deploy of na elke OM-reindex.
#
# Trigger:
#   make om-fix-search-mapping
#   OF: bash scripts/om-fix-search-mapping.sh

set -euo pipefail

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

OS_NS="${OS_NS:-uwv-meta}"
OS_POD="${OS_POD:-opensearch-uwv-master-0}"
OS_URL="${OS_URL:-http://localhost:9200}"

# Indices waarop OM aggregaties uitvoert in de Explore-UI.
INDICES=(
  table_search_index
  dashboard_search_index
  pipeline_search_index
  glossary_term_search_index
  database_search_index
  database_schema_search_index
  data_product_search_index
  domain_search_index
  user_search_index
  team_search_index
  topic_search_index
  container_search_index
  dashboard_data_model_search_index
  mlmodel_search_index
  search_service_search_index
  messaging_service_search_index
  pipeline_service_search_index
  dashboard_service_search_index
  storage_service_search_index
  database_service_search_index
)

MAPPING='{
  "properties": {
    "glossaryTags":         {"type":"text","fielddata":true,"fields":{"keyword":{"type":"keyword","ignore_above":256}}},
    "classificationTags":   {"type":"text","fielddata":true,"fields":{"keyword":{"type":"keyword","ignore_above":256}}},
    "deleted":              {"type":"text","fielddata":true,"fields":{"keyword":{"type":"keyword","ignore_above":256}}},
    "entityStatus":         {"type":"text","fielddata":true,"fields":{"keyword":{"type":"keyword","ignore_above":256}}}
  }
}'

if ! kubectl -n "$OS_NS" get pod "$OS_POD" >/dev/null 2>&1; then
  fail "OpenSearch pod $OS_NS/$OS_POD niet gevonden — installeer eerst infrastructure/helm/opensearch/."
fi

log "Patch OS-mappings voor ${#INDICES[@]} indices ($OS_NS/$OS_POD)"

failed=0
for idx in "${INDICES[@]}"; do
  code=$(kubectl -n "$OS_NS" exec "$OS_POD" -c opensearch -- \
    sh -c "curl -sS -o /dev/null -w '%{http_code}' -X PUT '$OS_URL/$idx/_mapping' \
      -H 'Content-Type: application/json' \
      -d '$MAPPING'" 2>/dev/null || echo "000")
  case "$code" in
    200|201) ok "$idx" ;;
    404)     warn "$idx (bestaat niet — sla over)" ;;
    *)       warn "$idx → HTTP $code"; failed=$((failed + 1)) ;;
  esac
done

if [[ $failed -gt 0 ]]; then
  warn "$failed indices niet gepatched — check OS-status."
fi

ok "OM-search mapping fix toegepast — OM UI Explore werkt weer."
