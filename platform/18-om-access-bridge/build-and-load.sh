#!/usr/bin/env bash
# Build het om-access-bridge image en importeer het in de lokale k3d-cluster.
#
# Idempotent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}/app"
IMAGE_TAG="${IMAGE_TAG:-odap/om-access-bridge:dev}"
CLUSTER_NAME="${CLUSTER_NAME:-odap-platform}"

echo "==> image tag:       ${IMAGE_TAG}"
echo "==> k3d cluster:     ${CLUSTER_NAME}"

echo "==> docker build"
docker build -t "${IMAGE_TAG}" "${APP_DIR}"

if ! k3d cluster list --no-headers | awk '{print $1}' | grep -qx "${CLUSTER_NAME}"; then
  echo "ERROR: k3d cluster '${CLUSTER_NAME}' not found." >&2
  echo "       Start it with:  make cluster" >&2
  exit 1
fi
echo "==> k3d image import"
k3d image import "${IMAGE_TAG}" -c "${CLUSTER_NAME}"

echo
echo "Image '${IMAGE_TAG}' is now available inside the '${CLUSTER_NAME}' cluster."
echo "Apply manifests with:"
echo "  kubectl apply -k ${SCRIPT_DIR}"
echo "Or trigger a rollout if already deployed:"
echo "  kubectl -n odap-platform rollout restart deploy/om-access-bridge"
