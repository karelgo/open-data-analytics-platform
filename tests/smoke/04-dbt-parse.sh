#!/usr/bin/env bash
# Validate the one active model graph without querying Trino.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
make dbt-parse
