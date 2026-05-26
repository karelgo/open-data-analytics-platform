#!/usr/bin/env bash
# Build the multica-daemon image and import it into the local k3d
# cluster (odap-platform).
#
# Idempotent and safe to re-run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_TAG="${IMAGE_TAG:-odap/multica-daemon:dev}"
CLUSTER_NAME="${CLUSTER_NAME:-odap-platform}"

echo "==> image tag:       ${IMAGE_TAG}"
echo "==> k3d cluster:     ${CLUSTER_NAME}"

# Build (build context is the daemon directory itself).
echo "==> docker build"
docker build -t "${IMAGE_TAG}" "${SCRIPT_DIR}"

# Import into k3d (skips a registry roundtrip).
if ! k3d cluster list --no-headers | awk '{print $1}' | grep -qx "${CLUSTER_NAME}"; then
  echo "ERROR: k3d cluster '${CLUSTER_NAME}' not found." >&2
  exit 1
fi
echo "==> k3d image import"
k3d image import "${IMAGE_TAG}" -c "${CLUSTER_NAME}"

echo
echo "Image '${IMAGE_TAG}' is now available inside the '${CLUSTER_NAME}' cluster."
echo "Apply manifests with:"
echo "  kubectl apply -k ${SCRIPT_DIR}"
echo "Or trigger a rollout if already deployed:"
echo "  kubectl -n odap-platform rollout restart deploy/multica-daemon"
