#!/usr/bin/env bash
# Compatibility alias: seed the one active job-market example.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/scripts/job-market-cluster.sh" "$@"
