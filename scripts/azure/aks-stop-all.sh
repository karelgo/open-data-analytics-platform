#!/usr/bin/env bash
# Stop AKS to save COMPUTE costs. For zero ongoing cost (including managed
# disks) run scripts/azure/aks-down-all.sh instead.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }

[[ -f scripts/azure/env.sh ]] && source scripts/azure/env.sh

log "Stopping AKS cluster (deallocates compute)"
bash scripts/azure/aks-stop.sh

cat <<'EOF'

  --- Cost note -------------------------------------------------
   AKS nodes:    deallocated (no compute charge).
   AKS disks:    a few €/month for the managed disks (PVCs).
                 Resume cluster: make aks-start
                 Full teardown:  make aks-down-all   (€0 after)
  ---------------------------------------------------------------
EOF
