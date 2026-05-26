#!/usr/bin/env bash
# Fetch AKS kubeconfig and switch kubectl context.
set -euo pipefail

log()   { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

RG="${AKS_RESOURCE_GROUP:-dev-stackable-rg}"
NAME="${AKS_CLUSTER_NAME:-odap-platform-aks}"

log "az aks get-credentials --resource-group $RG --name $NAME --overwrite-existing"
az aks get-credentials --resource-group "$RG" --name "$NAME" --overwrite-existing

log "Current context: $(kubectl config current-context)"
kubectl get nodes
