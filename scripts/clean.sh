#!/usr/bin/env bash
# Verwijder de k3d-cluster.
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-odap-platform}"

if ! command -v k3d >/dev/null 2>&1; then
  echo "ERROR: k3d niet gevonden." >&2
  exit 1
fi

if k3d cluster list -o json 2>/dev/null | jq -e ".[] | select(.name==\"${CLUSTER_NAME}\")" >/dev/null; then
  echo "==> Verwijderen k3d cluster '${CLUSTER_NAME}'"
  k3d cluster delete "$CLUSTER_NAME"
else
  echo "k3d cluster '${CLUSTER_NAME}' bestaat niet. Overslaan."
fi

echo
echo "Tip: for a complete reset (incl. volumes) ook k3d-volume opruimen:"
echo "  docker volume ls | awk '/odap-platform-data/ {print \$2}' | xargs -r docker volume rm"
