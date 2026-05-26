#!/usr/bin/env bash
# scripts/lib/log.sh — shared logging helpers.
#
# Replaces 8 ad-hoc `log()/warn()/fail()` definitions scattered across
# scripts/. Idempotent: safe to source multiple times.
#
# Usage:
#   ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
#   # shellcheck source=lib/log.sh
#   source "${ROOT}/scripts/lib/log.sh"
#
#   log   "starting deploy"           # blue ==>
#   info  "detail"                    # plain
#   warn  "something off"             # yellow !!
#   error "non-fatal error"           # red ERROR, returns 1
#   fail  "fatal error"               # red FAIL, exits 1
#
# Color discipline:
#   - `log`  → progress (top-level steps)
#   - `info` → detail (sub-step under a log)
#   - `warn` → recoverable (skipped step, version mismatch)
#   - `error`→ non-fatal (caller decides what to do)
#   - `fail` → fatal (exit 1)
#
# Honors NO_COLOR (https://no-color.org/) when stdout is not a TTY.

if [[ -n "${__LOG_LIB_LOADED:-}" ]]; then return 0; fi
__LOG_LIB_LOADED=1

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  __LOG_BLUE=$'\033[1;34m'
  __LOG_GREEN=$'\033[1;32m'
  __LOG_YELLOW=$'\033[1;33m'
  __LOG_RED=$'\033[1;31m'
  __LOG_RESET=$'\033[0m'
else
  __LOG_BLUE=''
  __LOG_GREEN=''
  __LOG_YELLOW=''
  __LOG_RED=''
  __LOG_RESET=''
fi

# Top-level progress
log() {
  printf '%s==>%s %s\n' "$__LOG_BLUE" "$__LOG_RESET" "$*"
}

# Sub-step detail (no color, no prefix)
info() {
  printf '    %s\n' "$*"
}

# Recoverable warning
warn() {
  printf '%s!!%s %s\n' "$__LOG_YELLOW" "$__LOG_RESET" "$*" >&2
}

# Non-fatal error — caller decides to continue or abort
error() {
  printf '%sERROR%s %s\n' "$__LOG_RED" "$__LOG_RESET" "$*" >&2
  return 1
}

# Fatal — print FAIL and exit 1
fail() {
  printf '%sFAIL%s %s\n' "$__LOG_RED" "$__LOG_RESET" "$*" >&2
  exit 1
}

# Test-success indicator (paired with `fail` in test runners).
pass() {
  printf '%sPASS%s %s\n' "$__LOG_GREEN" "$__LOG_RESET" "$*"
}
