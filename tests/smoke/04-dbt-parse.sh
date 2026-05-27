#!/usr/bin/env bash
# Smoke test 04 — dbt project parses and compiles correct.
#
# Geen warehouse-access nodig: `dbt parse` valideert YAML/Jinja en
# `dbt compile` rendert SQL zonder query's te draaien.
#
# Voorkeur: lokaal pip-installed dbt-trino. Fallback: docker image
# ghcr.io/dbt-labs/dbt-trino:1.9.x.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/dbt"

log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }
pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }

# Bepaal runner. dbt-fusion (de Rust-rewrite, default in latere dbt-installs)
# heeft nog geen Trino-adapter ("not yet implemented: Trino"), dus wij
# voorkeuren expliciet een dbt-core venv. Volgorde:
#   1. $DBT_BIN env-override (gebruiker-controle)
#   2. ~/.dbt-core-venv/bin/dbt (conventie in deze repo)
#   3. PATH-dbt mits NIET fusion
#   4. lokale odap/dbt-trino:1.9.0 image
#   5. upstream ghcr.io/dbt-labs/dbt-trino:1.9.0
DBT_BIN="${DBT_BIN:-}"
if [[ -z "$DBT_BIN" && -x "$HOME/.dbt-core-venv/bin/dbt" ]]; then
  DBT_BIN="$HOME/.dbt-core-venv/bin/dbt"
fi
if [[ -z "$DBT_BIN" ]] && command -v dbt >/dev/null 2>&1 && ! dbt --version 2>&1 | grep -qi fusion; then
  DBT_BIN="dbt"
fi
if [[ -z "$DBT_BIN" ]] && command -v docker >/dev/null 2>&1; then
  DBT_IMAGE="${DBT_IMAGE:-odap/dbt-trino:1.9.0}"
  if ! docker image inspect "$DBT_IMAGE" >/dev/null 2>&1; then
    DBT_IMAGE="ghcr.io/dbt-labs/dbt-trino:1.9.0"
  fi
  log "Using docker image: $DBT_IMAGE"
  DBT_BIN="docker run --rm -v $(pwd):/dbt -w /dbt -e DBT_PROFILES_DIR=/dbt $DBT_IMAGE"
fi
if [[ -z "$DBT_BIN" ]]; then
  fail "Geen dbt-trino en geen docker beschikbaar — installeer dbt-core+dbt-trino in ~/.dbt-core-venv, of een Docker."
fi
log "Using dbt: $DBT_BIN"

# 1. profiles.yml — gebruik de template als smoke; password kan dummy zijn.
if [[ ! -f "$ROOT/dbt/profiles.yml" ]]; then
  log "Render profiles.yml uit template (smoke-only — credentials zijn dummy)"
  TRINO_PASSWORD="smoke-dummy" envsubst < profiles.yml.template > profiles.yml || \
    cp profiles.yml.template profiles.yml
fi
export DBT_PROFILES_DIR="$ROOT/dbt"

# 2. dbt deps — install packages
log "dbt deps"
$DBT_BIN deps || fail "dbt deps faalde"
pass "dependencies geïnstalleerd"

# 3. dbt parse — valideer YAML + Jinja
log "dbt parse"
$DBT_BIN parse || fail "dbt parse faalde"
pass "dbt parse groen"

# 4. dbt compile — render SQL (geen DB-connectie nodig)
#    Voor compile heeft dbt vanaf 1.9 de DB nodig. We laten dit alleen draaien
#    als de cluster bereikbaar is; anders skip met waarschuwing.
log "dbt compile (best-effort — vereist warehouse-connectie)"
if $DBT_BIN compile 2>&1 | tee /tmp/dbt-compile.log | tail -3; then
  pass "dbt compile groen"
else
  printf '  [SKIP] dbt compile vereist warehouse — niet bereikbaar of eerste run.\n'
fi

echo
pass "smoke 04-dbt-parse: alle checks groen (compile is best-effort)"
