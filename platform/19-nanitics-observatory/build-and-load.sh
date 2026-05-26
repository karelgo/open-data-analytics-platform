#!/usr/bin/env bash
# Build the Nanitics Observatory image and import it into the local
# k3d cluster (odap-platform).
#
# Steps:
#   1) Locate the nanitics SDK repo (env var NANITICS_REPO or the default).
#   2) Sync observatory/dist-embed into ./app/observatory-ui (so Docker can COPY it).
#   3) docker build with ./app/ as the build context.
#   4) k3d image import into the odap-platform cluster (no registry needed).
#
# Idempotent and safe to re-run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}/app"
NANITICS_REPO="${NANITICS_REPO:-/Users/karelgoense/Documents/programming/sandbox/nanitics}"
IMAGE_TAG="${IMAGE_TAG:-odap/nanitics-observatory:dev}"
CLUSTER_NAME="${CLUSTER_NAME:-odap-platform}"

echo "==> nanitics repo:   ${NANITICS_REPO}"
echo "==> image tag:       ${IMAGE_TAG}"
echo "==> k3d cluster:     ${CLUSTER_NAME}"

# 1) Sanity-check the nanitics repo + dist-embed bundle.
DIST_EMBED="${NANITICS_REPO}/observatory/dist-embed"
if [[ ! -d "${DIST_EMBED}" ]]; then
  echo "ERROR: dist-embed bundle not found at ${DIST_EMBED}." >&2
  echo "       From the nanitics repo, run:  just observatory-build" >&2
  exit 1
fi

# 2) Sync the bundle into the build context. rsync if available
#    (preserves permissions, deletes stale files); cp -R as fallback.
TARGET="${APP_DIR}/observatory-ui"
echo "==> Syncing dist-embed -> ${TARGET}"
mkdir -p "${TARGET}"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "${DIST_EMBED}/" "${TARGET}/"
else
  rm -rf "${TARGET}"
  cp -R "${DIST_EMBED}" "${TARGET}"
fi

# 3) Build.
echo "==> docker build"
docker build -t "${IMAGE_TAG}" "${APP_DIR}"

# 4) Import into k3d (skips a registry roundtrip).
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
echo "  kubectl -n odap-platform rollout restart deploy/nanitics-observatory"
