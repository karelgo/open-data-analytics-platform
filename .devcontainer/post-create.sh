#!/usr/bin/env bash
# Post-create stap for the UDP devcontainer / GitHub Codespace.
# Doel: alle CLI's die in de Academy-modules genoemd worden meteen werken.

set -euo pipefail

echo "─── installing python deps ───"
python -m pip install --upgrade pip
python -m pip install \
  'dbt-trino>=1.8' \
  'pre-commit>=3.7' \
  'pytest>=8' \
  'requests>=2.32' \
  'jupyter>=1.0' \
  'pandas>=2.2'

echo "─── installing stackablectl ───"
# https://github.com/stackabletech/stackable-cockpit/releases
STACKABLE_VERSION="${STACKABLE_VERSION:-25.7.0}"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)  PLATFORM="x86_64-unknown-linux-gnu" ;;
  aarch64) PLATFORM="aarch64-unknown-linux-gnu" ;;
  *) echo "warn: stackablectl niet voor $ARCH"; exit 0 ;;
esac
URL="https://github.com/stackabletech/stackable-cockpit/releases/download/stackablectl-${STACKABLE_VERSION}/stackablectl-${PLATFORM}"
sudo curl -fL --retry 3 -o /usr/local/bin/stackablectl "$URL"
sudo chmod +x /usr/local/bin/stackablectl

echo "─── pre-commit hooks ───"
if [ -f .pre-commit-config.yaml ]; then
  pre-commit install --install-hooks || true
fi

echo "─── portal node deps ───"
if [ -d portal ]; then
  (cd portal && npm install --no-fund --no-audit)
fi

echo "─── done ───"
echo
echo "Probeer:"
echo "  cd portal && npm run dev   # Academy lokaal op :4321"
echo "  make help                  # alle make-targets"
