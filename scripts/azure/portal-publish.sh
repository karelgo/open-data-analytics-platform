#!/usr/bin/env bash
# Build (or re-build) the Astro portal under portal/, package the static
# output into a binaryData ConfigMap, and roll the platform-landing
# Deployment so it picks up the new bundle.
#
# This avoids the need for an image registry — `dist/` lives in a ConfigMap
# (~312 KB compressed, well under the 1 MiB ConfigMap limit), an
# initContainer extracts it into emptyDir on pod start, and stock
# nginxinc/nginx-unprivileged serves from there.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

log()   { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
error() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

ctx="$(kubectl config current-context 2>/dev/null || true)"
case "$ctx" in
  odap-platform-aks|*aks*) ;;
  *) error "kubectl context is '$ctx', not the AKS cluster. Run: make aks-context" ;;
esac

if [[ ! -d portal/dist || -z "$(ls -A portal/dist 2>/dev/null)" ]]; then
  log "portal/dist is missing — building (npm install + astro build)"
  (cd portal && npm install --no-audit --no-fund && npm run build)
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

log "Packaging portal/dist -> $TMP/portal-dist.tar.gz"
tar czf "$TMP/portal-dist.tar.gz" -C portal/dist .
SIZE=$(wc -c <"$TMP/portal-dist.tar.gz")
log "Tarball size: $SIZE bytes"
if (( SIZE > 1000000 )); then
  error "Tarball is larger than 1 MB — ConfigMap won't accept it. Switch to a registry or split."
fi
CHECKSUM=$(shasum -a 256 "$TMP/portal-dist.tar.gz" | cut -c1-12)

log "Apply ConfigMap platform-landing-dist (binaryData)"
# kubectl apply records the whole resource as a metadata annotation (limit
# 256 KB) — so for >256 KB tarballs we delete-and-create instead. The
# Deployment is rolled in the next step regardless, so the brief gap is fine.
kubectl -n odap-platform delete configmap platform-landing-dist --ignore-not-found >/dev/null
kubectl -n odap-platform create configmap platform-landing-dist \
  --from-file=portal-dist.tar.gz="$TMP/portal-dist.tar.gz" >/dev/null

log "Roll the Deployment so the initContainer re-extracts the new tarball"
kubectl -n odap-platform patch deployment platform-landing \
  --type=merge -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"portal.odap/dist-checksum\":\"$CHECKSUM\"}}}}}" >/dev/null
kubectl -n odap-platform rollout status deploy/platform-landing --timeout=120s

log "Done. Browse https://platform.odap-platform.cloud:8443/"
