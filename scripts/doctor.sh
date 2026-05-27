#!/usr/bin/env bash
# Doctor — controleer of de host de vereiste tooling heeft.
#
# Mode-aware: --mode=k3d (default) | aks bepaalt welke tools en
# /etc/hosts entries gecheckt worden. Voor aks zijn k3d en /etc/hosts
# niet nodig; azure-cli is wel verplicht.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=lib/mode.sh
source "${ROOT}/scripts/lib/mode.sh"
parse_mode_args "$@"

# Tools required for every mode.
common_required=(
  "kubectl    version 1.29+"
  "helm       version 3.14+"
  "stackablectl version 25+ (https://github.com/stackabletech/stackable-cockpit)"
  "jq         (JSON in shells)"
  "yq         (YAML in shells)"
  "opa        (Rego)"
  "python3    3.11+"
)

# Mode-specific required tools.
case "$DEPLOYMENT_MODE" in
  k3d)
    mode_required=("docker     version 24+"
                   "k3d        version 5.6+")
    ;;
  aks)
    mode_required=("az         (Azure CLI)"
                   "terraform  version 1.5+")
    ;;
  stackit)
    mode_required=("stackit    (StackIT CLI)"
                   "az         (Azure CLI — DNS lives in Azure DNS)"
                   "terraform  version 1.5+")
    ;;
esac

optional=(
  "mc         (MinIO client — handig voor seed)"
  "psql       (PostgreSQL client)"
  "yamllint   (CI lint)"
  "ruff       (Python lint)"
)

missing=0
warn_count=0

check() {
  local name="$1"
  local critical="$2"
  if command -v "$name" >/dev/null 2>&1; then
    printf "  [OK]   %-12s -> %s\n" "$name" "$(command -v "$name")"
  else
    if [[ "$critical" == "yes" ]]; then
      printf "  [MISS] %-12s\n" "$name"
      missing=$((missing+1))
    else
      printf "  [warn] %-12s (optioneel)\n" "$name"
      warn_count=$((warn_count+1))
    fi
  fi
}

echo "== Mode: $DEPLOYMENT_MODE  (domain=$PLATFORM_DOMAIN, port=$PLATFORM_PORT) =="

echo
echo "== Requirede tooling (gemeenschappelijk) =="
for line in "${common_required[@]}"; do
  check "${line%% *}" yes
done

echo
echo "== Requirede tooling (mode=$DEPLOYMENT_MODE) =="
for line in "${mode_required[@]}"; do
  check "${line%% *}" yes
done

echo
echo "== Optionele tooling =="
for line in "${optional[@]}"; do
  check "${line%% *}" no
done

# /etc/hosts check — alleen relevant voor lokale modes.
hosts_missing=0
if [[ "$IS_LOCAL" == "yes" ]]; then
  echo
  echo "== /etc/hosts check (*.${PLATFORM_DOMAIN}) =="
  hosts=(
    trino keycloak superset airflow minio minio-console
    openmetadata grafana spark jupyter
  )
  for sub in "${hosts[@]}"; do
    fqdn="${sub}.${PLATFORM_DOMAIN}"
    if grep -q "$fqdn" /etc/hosts 2>/dev/null; then
      printf "  [OK]   %s\n" "$fqdn"
    else
      printf "  [MISS] %s\n" "$fqdn"
      hosts_missing=$((hosts_missing+1))
    fi
  done

  if [[ $hosts_missing -gt 0 ]]; then
    echo
    echo "Voeg toe aan /etc/hosts (sudo vereist):"
    hostline="127.0.0.1"
    for sub in "${hosts[@]}"; do hostline="$hostline ${sub}.${PLATFORM_DOMAIN}"; done
    echo "  $hostline"
  fi
fi

# Kubectl context check — alleen waarschuwen als er een context is en die
# afwijkt van de gekozen mode. Voor een verse install bestaat er nog niets.
echo
echo "== kubectl context vs mode =="
ctx="$(kubectl config current-context 2>/dev/null || true)"
if [[ -z "$ctx" ]]; then
  printf "  [warn] geen kubectl context — run 'make cluster MODE=%s' (lokaal) of 'make aks-context' (cloud)\n" "$DEPLOYMENT_MODE"
else
  case "$DEPLOYMENT_MODE" in
    stackit)
      if [[ "$ctx" == *stackit* ]]; then printf "  [OK]   context '%s' past bij mode=stackit\n" "$ctx"
      else printf "  [warn] context '%s' is geen StackIT-context (mode=stackit verwacht)\n" "$ctx"
      fi ;;
    k3d)
      if [[ "$ctx" == k3d-* ]]; then printf "  [OK]   context '%s' past bij mode=k3d\n" "$ctx"
      else printf "  [warn] context '%s' is geen k3d-context (mode=k3d verwacht)\n" "$ctx"
      fi ;;
    aks)
      if [[ "$ctx" == *aks* ]]; then printf "  [OK]   context '%s' past bij mode=aks\n" "$ctx"
      else printf "  [warn] context '%s' is geen AKS-context (mode=aks verwacht)\n" "$ctx"
      fi ;;
  esac
fi

echo
if [[ $missing -gt 0 || $hosts_missing -gt 0 ]]; then
  echo "FAIL: ontbrekende vereisten (missing=$missing, /etc/hosts=$hosts_missing)."
  exit 1
fi

echo "OK: alle vereiste tooling aanwezig voor mode=$DEPLOYMENT_MODE."
[[ $warn_count -gt 0 ]] && echo "  ($warn_count optionele tools ontbreken — niet blokkerend)"

# Azure account check — alleen relevant voor aks.
if [[ "$DEPLOYMENT_MODE" == "aks" ]]; then
  echo
  echo "== Azure / AKS readiness =="
  if [[ -f "$ROOT/scripts/azure/env.sh" ]]; then
    printf "  [OK]   %-12s -> %s\n" "env.sh" "$ROOT/scripts/azure/env.sh"
  else
    printf "  [warn] %-12s (kopieer scripts/azure/env.sh.example en vul de SP-secret in)\n" "env.sh"
  fi
  if command -v az >/dev/null 2>&1; then
    acct="$(az account show --query name -o tsv 2>/dev/null || true)"
    if [[ -n "$acct" ]]; then
      printf "  [OK]   az login        -> %s\n" "$acct"
    else
      printf "  [warn] az login        (nog niet ingelogd: az login)\n"
    fi
  fi
fi
