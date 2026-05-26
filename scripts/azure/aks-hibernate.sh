#!/usr/bin/env bash
# Aggressively minimize Azure spend while the AKS cluster is offline.
#
# When you run `az aks stop`, the node VMs deallocate (compute → €0) but the
# PVC-managed disks keep billing. For our stack that's ~€20/month in detached
# StandardSSD + 1 Premium P10 (MinIO, 100 GB ≈ €15/month on its own).
#
# `hibernate down` snapshots every unattached PVC disk and deletes the disk
# itself. Incremental snapshots are roughly 3-4× cheaper than the disk per GB,
# so this drops the stopped-state cost from ~€27/month to ~€11/month.
#
# `hibernate up` recreates each disk *with the same name* from its snapshot.
# Azure resource IDs are deterministic (subscription + RG + name) so the PVs
# don't need patching — they still point at the same disk resource ID.
#
# `hibernate status` prints what's currently provisioned + the rough monthly
# cost so you can decide whether down/up is worth it.
#
# Usage:
#   bash scripts/azure/aks-hibernate.sh down     # stop + snapshot + delete disks
#   bash scripts/azure/aks-hibernate.sh up       # recreate disks + start cluster
#   bash scripts/azure/aks-hibernate.sh status   # show state + cost estimate
#
# NB: don't run `make aks-start` directly after `hibernate down` — the pods
# will crash-loop because their underlying disks are gone. Always go through
# `hibernate up`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ -f "$ROOT/scripts/azure/env.sh" ]] && source "$ROOT/scripts/azure/env.sh"

RG="${AKS_RESOURCE_GROUP:-dev-stackable-rg}"
CLUSTER="${AKS_CLUSTER_NAME:-odap-platform-aks}"
REGION="${AKS_REGION:-westeurope}"
NODE_RG="MC_${RG}_${CLUSTER}_${REGION}"
SNAP_SUFFIX="hibernate"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

cmd="${1:-status}"

cluster_state() {
  az aks show -g "$RG" -n "$CLUSTER" --query powerState.code -o tsv 2>/dev/null || echo "Unknown"
}

# Best-effort monthly cost estimate (West Europe, May 2026, eur, pay-as-you-go).
# Numbers are approximate and ignore data transfer.
estimate_cost() {
  local total=0
  # Disks
  while IFS=$'\t' read -r name gb sku; do
    [[ -z "$name" ]] && continue
    # Bucket size into Azure's billed tier
    local bucket
    if   (( gb <= 4   )); then bucket=4
    elif (( gb <= 8   )); then bucket=8
    elif (( gb <= 16  )); then bucket=16
    elif (( gb <= 32  )); then bucket=32
    elif (( gb <= 64  )); then bucket=64
    elif (( gb <= 128 )); then bucket=128
    elif (( gb <= 256 )); then bucket=256
    else                       bucket=$gb
    fi
    local rate=0
    case "$sku" in
      Premium_LRS)     rate=$(awk -v g="$bucket" 'BEGIN{print g*0.12}') ;;  # ~€0.12/GB/mo
      StandardSSD_LRS) rate=$(awk -v g="$bucket" 'BEGIN{print g*0.064}') ;; # ~€0.064/GB/mo
      Standard_LRS)    rate=$(awk -v g="$bucket" 'BEGIN{print g*0.043}') ;; # ~€0.043/GB/mo
    esac
    total=$(awk -v t="$total" -v r="$rate" 'BEGIN{printf "%.2f", t+r}')
  done < <(az disk list -g "$NODE_RG" -o tsv --query "[].[name, diskSizeGB, sku.name]" 2>/dev/null)
  # Snapshots (incremental, ~€0.045/GB/mo on top of any deltas)
  while IFS=$'\t' read -r name gb; do
    [[ -z "$name" ]] && continue
    total=$(awk -v t="$total" -v g="$gb" 'BEGIN{printf "%.2f", t+g*0.045}')
  done < <(az snapshot list -g "$NODE_RG" -o tsv --query "[].[name, diskSizeGB]" 2>/dev/null)
  # Public IPs (Standard SKU, ~€3/mo each)
  local pip_count=$(az network public-ip list -g "$NODE_RG" --query "length([?sku.name=='Standard'])" -o tsv 2>/dev/null || echo 0)
  total=$(awk -v t="$total" -v n="$pip_count" 'BEGIN{printf "%.2f", t+n*3}')
  echo "$total"
}

case "$cmd" in
  status)
    state=$(cluster_state)
    log "AKS cluster: $CLUSTER → $state"
    echo
    echo "  Detached disks:"
    az disk list -g "$NODE_RG" \
      --query "[?diskState=='Unattached'].{tag:tags.\"kubernetes.io-created-for-pvc-name\", gb:diskSizeGB, sku:sku.name}" \
      -o table 2>/dev/null || echo "    (none)"
    echo
    echo "  Attached disks:"
    attached=$(az disk list -g "$NODE_RG" --query "length([?diskState=='Attached'])" -o tsv 2>/dev/null || echo 0)
    echo "    $attached"
    echo
    echo "  Hibernate snapshots:"
    az snapshot list -g "$NODE_RG" \
      --query "[?ends_with(name, '-${SNAP_SUFFIX}')].{name:name, gb:diskSizeGB, sku:sku.name}" \
      -o table 2>/dev/null || echo "    (none)"
    echo
    echo "  Public IPs:"
    az network public-ip list -g "$NODE_RG" \
      --query "[].{name:name, ip:ipAddress, sku:sku.name}" -o table 2>/dev/null
    echo
    cost=$(estimate_cost)
    log "Estimated monthly cost (disks+snapshots+PIPs): €$cost"
    echo "  Note: excludes data transfer, LB rules, DNS zone, App Service Domain (~€1/mo)."
    ;;

  down)
    state=$(cluster_state)
    if [[ "$state" != "Stopped" ]]; then
      log "Cluster is $state — stopping first (this can take ~5 min)"
      az aks stop -g "$RG" -n "$CLUSTER"
    fi

    # Refuse if there are still attached disks (would mean stop didn't fully release)
    attached=$(az disk list -g "$NODE_RG" --query "length([?diskState=='Attached'])" -o tsv)
    if (( attached > 0 )); then
      err "$attached disks still Attached. Wait a minute for VMSS deallocation and retry."
    fi

    DISKS=()
    while IFS= read -r line; do
      [[ -n "$line" ]] && DISKS+=("$line")
    done < <(az disk list -g "$NODE_RG" \
      --query "[?diskState=='Unattached'].name" -o tsv)
    log "Snapshotting & deleting ${#DISKS[@]} disks"
    for d in "${DISKS[@]}"; do
      snap="${d}-${SNAP_SUFFIX}"
      if az snapshot show -g "$NODE_RG" -n "$snap" >/dev/null 2>&1; then
        log "  snapshot $snap already exists — skip"
      else
        # Capture SKU on the snapshot tag so `up` can restore the right tier
        info=$(az disk show -g "$NODE_RG" -n "$d" \
          --query "{id:id, sku:sku.name, gb:diskSizeGB}" -o tsv)
        diskId=$(awk '{print $1}' <<<"$info")
        diskSku=$(awk '{print $2}' <<<"$info")
        diskGb=$(awk '{print $3}' <<<"$info")
        log "  snapshot $snap ($diskGb GB, $diskSku)"
        az snapshot create -g "$NODE_RG" -n "$snap" \
          --source "$diskId" --incremental true \
          --tags originalSku="$diskSku" originalGb="$diskGb" originalName="$d" \
          -o none
      fi
      log "  delete disk $d"
      az disk delete -g "$NODE_RG" -n "$d" --yes --no-wait
    done
    log "Hibernate down complete."
    log "Run 'bash scripts/azure/aks-hibernate.sh status' to verify."
    log "Wake up later with: bash scripts/azure/aks-hibernate.sh up"
    ;;

  up)
    SNAPS=()
    while IFS= read -r line; do
      [[ -n "$line" ]] && SNAPS+=("$line")
    done < <(az snapshot list -g "$NODE_RG" \
      --query "[?ends_with(name, '-${SNAP_SUFFIX}')].name" -o tsv)
    if (( ${#SNAPS[@]} == 0 )); then
      warn "No hibernate snapshots found. If cluster has its disks, just run 'make aks-start'."
    fi
    log "Restoring ${#SNAPS[@]} disks from snapshots"
    for s in "${SNAPS[@]}"; do
      disk="${s%-${SNAP_SUFFIX}}"
      if az disk show -g "$NODE_RG" -n "$disk" >/dev/null 2>&1; then
        log "  disk $disk already exists — skip"
      else
        sku=$(az snapshot show -g "$NODE_RG" -n "$s" \
          --query "tags.originalSku" -o tsv 2>/dev/null)
        sku="${sku:-StandardSSD_LRS}"
        snapId=$(az snapshot show -g "$NODE_RG" -n "$s" --query id -o tsv)
        log "  recreate $disk from $s ($sku)"
        az disk create -g "$NODE_RG" -n "$disk" \
          --source "$snapId" --sku "$sku" -o none
      fi
    done

    state=$(cluster_state)
    if [[ "$state" == "Running" ]]; then
      log "Cluster already running."
    else
      log "Starting cluster $CLUSTER (this can take ~5 min)"
      az aks start -g "$RG" -n "$CLUSTER"
    fi

    log "Wake complete. Snapshots are kept until you delete them — they bill ~25% of disk cost."
    log "When pods are healthy, delete the snapshots:"
    log "  az snapshot delete -g $NODE_RG --ids \$(az snapshot list -g $NODE_RG --query \"[?ends_with(name, '-${SNAP_SUFFIX}')].id\" -o tsv)"
    log "Or just leave them as a recovery point."
    ;;

  *)
    echo "Usage: $0 {down|up|status}" >&2
    exit 2
    ;;
esac
