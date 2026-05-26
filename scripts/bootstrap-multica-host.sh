#!/usr/bin/env bash
# One-time host setup for the cluster Multica:
#   1. Add multica.odap.local to /etc/hosts (so DNS resolves)
#   2. Trust the cluster CA in macOS Keychain (so TLS validation passes)
#
# Run from repo root with sudo; idempotent (skips entries that already exist).
#   sudo bash scripts/bootstrap-multica-host.sh
#
# Same setup pattern that the README expects for trino / superset / etc.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: this script needs root (it edits /etc/hosts and the System keychain)."
  echo "Re-run with: sudo bash $0"
  exit 1
fi

HOSTS_LINE="127.0.0.1 multica.odap.local"
if grep -qE "^[^#]*multica\.odap-platform\.local" /etc/hosts; then
  echo "/etc/hosts already has multica.odap.local — skipping."
else
  echo "$HOSTS_LINE" >> /etc/hosts
  echo "Added to /etc/hosts: $HOSTS_LINE"
fi

# Pull cluster CA from the multica-tls Secret. We use SUDO_USER's kubectl
# context so kubectl works (kubectl config typically lives under $HOME).
KUBE_USER="${SUDO_USER:-$USER}"
KUBE_HOME=$(eval echo "~$KUBE_USER")
export KUBECONFIG="${KUBECONFIG:-$KUBE_HOME/.kube/config}"

CA_FILE=/tmp/odap-platform-ca.crt
sudo -u "$KUBE_USER" kubectl -n odap-platform get secret multica-tls \
  -o jsonpath='{.data.ca\.crt}' 2>/dev/null \
  | base64 -d > "$CA_FILE"
if [ ! -s "$CA_FILE" ]; then
  echo "WARN: could not read multica-tls CA (is multica deployed yet?). Skipping CA trust."
  echo "      Re-run after 'kubectl apply -k platform/17-multica/'."
  exit 0
fi

# Idempotent: search by SHA1 fingerprint of the cert.
FINGERPRINT=$(openssl x509 -in "$CA_FILE" -noout -fingerprint -sha1 \
  | sed -E 's/^.*=//; s/://g')
if security find-certificate -a -Z /Library/Keychains/System.keychain 2>/dev/null \
   | grep -q "$FINGERPRINT"; then
  echo "Cluster CA already trusted — skipping."
else
  security add-trusted-cert -d -r trustRoot \
    -k /Library/Keychains/System.keychain "$CA_FILE"
  echo "Cluster CA added to System keychain (root trust)."
fi

rm -f "$CA_FILE"
echo "Done. multica.odap.local is now reachable with valid TLS."
