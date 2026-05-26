#!/usr/bin/env bash
# Resume a stopped AKS cluster.
#
# If the cluster was put to sleep with `make aks-hibernate` (PVC disks
# snapshotted + deleted), `az aks start` alone would bring the nodes back but
# every stateful pod (Postgres, MinIO, Stackable, …) would crash-loop on
# missing volume. So we detect that case and refuse — pointing at
# `make aks-wake` which restores the disks first.
set -euo pipefail

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

RG="${AKS_RESOURCE_GROUP:-dev-stackable-rg}"
NAME="${AKS_CLUSTER_NAME:-odap-platform-aks}"
REGION="${AKS_REGION:-westeurope}"
NODE_RG="MC_${RG}_${NAME}_${REGION}"

# Refuse if hibernated (snapshots exist + zero disks)
snap_count=$(az snapshot list -g "$NODE_RG" \
  --query "length([?ends_with(name, '-hibernate')])" -o tsv 2>/dev/null || echo 0)
disk_count=$(az disk list -g "$NODE_RG" --query "length(@)" -o tsv 2>/dev/null || echo 0)
if (( snap_count > 0 )) && (( disk_count == 0 )); then
  err "Cluster is hibernated ($snap_count snapshots, 0 disks). Run: make aks-wake"
fi

log "Starting AKS cluster '$NAME' in '$RG'"
az aks start --resource-group "$RG" --name "$NAME"

log "Started. Refresh kubeconfig: make aks-context"
