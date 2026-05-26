#!/usr/bin/env bash
# scripts/lib/mode.sh — single source of truth for deployment-mode handling.
#
# Sourced by the top-level scripts (bootstrap, deploy-platform, full-deploy,
# doctor). Parses --mode / DEPLOYMENT_MODE, validates that kubectl context
# matches the declared mode, and exposes mode-aware helpers:
#
#   chart_value_args <chart>   -- echo --values flags for base + mode override
#   kustomize_overlay <comp>   -- echo platform/<comp>/overlays/<mode> or
#                                  platform/<comp> for components that don't
#                                  yet have overlays
#   require_context            -- fail fast if kubectl context disagrees with mode
#
# After sourcing this file, the following vars are set:
#   DEPLOYMENT_MODE   -- one of k3d | aks | stackit
#   PLATFORM_DOMAIN   -- e.g. odap.local (k3d), example.com (aks),
#                              or example.com (stackit)
#   PLATFORM_PORT     -- 8443 (k3d) or 443 (aks|stackit). Browser URL port.
#   IS_LOCAL          -- "yes" for k3d, "no" for aks|stackit
#   IS_CLOUD          -- inverse of IS_LOCAL
#
# Usage from a script:
#   source "${ROOT}/scripts/lib/mode.sh"
#   parse_mode_args "$@"
#   require_context

# Avoid double-sourcing.
if [[ -n "${__MODE_LIB_LOADED:-}" ]]; then return 0; fi
__MODE_LIB_LOADED=1

# ---- logging helpers ----
# Always define our shell functions. We can't use `type log >/dev/null` to
# skip — on macOS `log` is a system binary (Console.app's CLI), so the
# check would always be truthy and our calls would fall through to it.
# `declare -F` only matches shell functions, so we check that.
declare -F log   >/dev/null || log()   { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
declare -F ok    >/dev/null || ok()    { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
declare -F warn  >/dev/null || warn()  { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
declare -F error >/dev/null || error() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

# ---- mode parsing -----------------------------------------------------
# Accepts:
#   --mode k3d | --mode=k3d | DEPLOYMENT_MODE env var
# Leaves remaining args (filtered) in the global REMAINING_ARGS array so
# callers can keep their own flag parsing.
parse_mode_args() {
  REMAINING_ARGS=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode)   DEPLOYMENT_MODE="$2"; shift 2 ;;
      --mode=*) DEPLOYMENT_MODE="${1#*=}"; shift ;;
      *)        REMAINING_ARGS+=("$1"); shift ;;
    esac
  done

  # Default to k3d (developer-laptop scenario). Env var beats default;
  # explicit flag beats env var.
  DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-${MODE:-k3d}}"

  case "$DEPLOYMENT_MODE" in
    k3d|aks|stackit) ;;
    *) error "Unknown --mode='$DEPLOYMENT_MODE'. Valid: k3d, aks, stackit." ;;
  esac

  # Domain / port defaults per mode. Override via PLATFORM_DOMAIN env var.
  case "$DEPLOYMENT_MODE" in
    k3d)
      PLATFORM_DOMAIN="${PLATFORM_DOMAIN:-odap.local}"
      PLATFORM_PORT="${PLATFORM_PORT:-8443}"
      IS_LOCAL="yes"; IS_CLOUD="no"
      ;;
    aks)
      PLATFORM_DOMAIN="${PLATFORM_DOMAIN:-example.com}"
      PLATFORM_PORT="${PLATFORM_PORT:-443}"
      IS_LOCAL="no"; IS_CLOUD="yes"
      ;;
    stackit)
      PLATFORM_DOMAIN="${PLATFORM_DOMAIN:-example.com}"
      PLATFORM_PORT="${PLATFORM_PORT:-443}"
      IS_LOCAL="no"; IS_CLOUD="yes"
      ;;
  esac

  export DEPLOYMENT_MODE PLATFORM_DOMAIN PLATFORM_PORT IS_LOCAL IS_CLOUD

  # HELM_OVERRIDES_DIR was the pre-Phase-1 way to select AKS overlays. It has
  # been removed; warn loudly if someone still sets it so the regression is
  # visible rather than silent.
  if [[ -n "${HELM_OVERRIDES_DIR:-}" ]]; then
    warn "HELM_OVERRIDES_DIR is no longer used. Pass --mode=aks (or set DEPLOYMENT_MODE=aks)."
  fi
}

# ---- helm value-file resolution --------------------------------------
# Returns --values flags for:
#   1. infrastructure/helm/<chart>/values.yaml       (mode-agnostic base)
#   2. infrastructure/helm/<chart>/values-<mode>.yaml (if present)
#
# Echo'd as a single string suitable for word-splitting in the helm cmd.
chart_value_args() {
  local chart="$1"
  local args=""
  local base="${ROOT}/infrastructure/helm/${chart}/values.yaml"
  local mode_file="${ROOT}/infrastructure/helm/${chart}/values-${DEPLOYMENT_MODE}.yaml"

  [[ -f "$base" ]] && args="--values ${base}"
  if [[ -f "$mode_file" ]]; then
    args="${args} --values ${mode_file}"
  fi
  printf '%s' "$args"
}

# ---- kustomize overlay resolution ------------------------------------
# Returns the kustomize directory to apply for a given platform component.
# Looks up platform-overlays/<mode>/<short>/ first (where <short> is the
# basename of `comp`, e.g. "07-nifi") — overlays live in a sibling tree
# rather than inside platform/<comp>/ because kustomize refuses to load
# an overlay that lives inside its own base's directory tree (cycle
# detection). If no overlay exists for this mode, falls back to the flat
# layout at platform/<comp>/.
kustomize_overlay() {
  local comp="$1"
  local short="${comp#platform/}"
  local overlay="${ROOT}/platform-overlays/${DEPLOYMENT_MODE}/${short}"
  if [[ -d "$overlay" && -f "${overlay}/kustomization.yaml" ]]; then
    printf '%s' "$overlay"
  else
    printf '%s' "${ROOT}/${comp}"
  fi
}

# ---- kubectl context guard -------------------------------------------
# Refuse to run if the current kubectl context doesn't match the declared
# mode. Heuristic, but catches the common "I forgot to switch context"
# mistake that silently nukes the wrong cluster.
require_context() {
  local ctx
  ctx="$(kubectl config current-context 2>/dev/null || true)"
  if [[ -z "$ctx" ]]; then
    error "no kubectl context set. Run 'make cluster' (k3d), 'make aks-context' (aks), or 'export KUBECONFIG=infrastructure/stackit/terraform/kubeconfig.yaml' (stackit)."
  fi
  case "$DEPLOYMENT_MODE" in
    k3d)
      [[ "$ctx" == k3d-* ]] \
        || error "mode=k3d but kubectl context '$ctx' is not a k3d cluster. Run 'make cluster'."
      ;;
    aks)
      case "$ctx" in
        odap-platform-aks|*aks*) ;;
        *) error "mode=aks but kubectl context '$ctx' is not an AKS cluster. Run 'make aks-context'." ;;
      esac
      ;;
    stackit)
      case "$ctx" in
        udp-stackit|*stackit*) ;;
        *) error "mode=stackit but kubectl context '$ctx' is not a StackIT SKE cluster. Run 'export KUBECONFIG=infrastructure/stackit/terraform/kubeconfig.yaml'." ;;
      esac
      ;;
  esac
  log "mode=$DEPLOYMENT_MODE  context=$ctx  domain=$PLATFORM_DOMAIN"
}

# ---- storage-class sanity check --------------------------------------
# Warns (does not fail) if the storage class the chosen mode expects isn't
# present on the cluster. PVCs would otherwise hang in Pending forever.
require_storage_class() {
  local expected
  case "$DEPLOYMENT_MODE" in
    k3d)     expected="local-path" ;;
    aks)     expected="managed-csi" ;;
    stackit) expected="premium-perf1-stackit" ;;
  esac
  if ! kubectl get storageclass "$expected" >/dev/null 2>&1; then
    warn "expected StorageClass '$expected' not found in cluster (mode=$DEPLOYMENT_MODE)."
    warn "PVCs will hang in Pending until a default StorageClass exists."
    kubectl get storageclass 2>/dev/null || true
  fi
}
