#!/usr/bin/env bash
# Importeer de persistente odap-platform CA in de macOS System Keychain.
#
# Idempotent: oude entries met dezelfde Common Name worden eerst verwijderd
# (er kunnen er meerdere zijn als de vorige workflow elke cluster-wipe een
# nieuw cert toevoegde), daarna wordt de huidige CA opnieuw geïmporteerd.
#
# Eénmalig per dev-machine. Daarna blijft de trust geldig over cluster-wipes
# heen, doordat scripts/bootstrap.sh de CA niet meer regenereert.
#
# Linux: voeg ~/.config/odap/ca/tls.crt toe aan je distro's
# trust-store (Debian/Ubuntu: cp naar /usr/local/share/ca-certificates/
# en run sudo update-ca-certificates).

set -euo pipefail

CA_CRT="${CA_DIR:-${HOME}/.config/odap/ca}/tls.crt"
CN="Open Data & Analytics Platform Self-Signed CA"

if [[ ! -f "$CA_CRT" ]]; then
  printf '\033[1;31mFAIL\033[0m %s\n' "${CA_CRT} bestaat niet — run eerst 'make bootstrap'." >&2
  exit 1
fi

if [[ "$(uname)" != "Darwin" ]]; then
  printf '\033[1;31mFAIL\033[0m %s\n' "trust-ca is alleen voor macOS. Voor Linux: zie comment bovenaan dit script." >&2
  exit 1
fi

# Loop: delete-certificate verwijdert één entry per call. Kan meerdere
# stale kopieën hebben uit de oude (regenererende) workflow.
removed=0
while sudo security delete-certificate -c "$CN" /Library/Keychains/System.keychain 2>/dev/null; do
  removed=$((removed + 1))
done
if [[ $removed -gt 0 ]]; then
  printf '\033[1;34m==>\033[0m %s\n' "${removed} oude CA-entries verwijderd uit de keychain"
fi

sudo security add-trusted-cert -d -r trustRoot -p ssl \
  -k /Library/Keychains/System.keychain "$CA_CRT"

printf '\033[1;32mOK\033[0m %s\n' "CA geïmporteerd in System Keychain."
echo
echo "Volgende stappen (eenmalig per browser):"
echo "  1. Cmd+Q je browser volledig (niet alleen het venster sluiten)."
echo "  2. Open chrome://net-internals/#hsts → Delete domain security policies"
echo "     en delete één voor één: platform / jupyter / superset / airflow /"
echo "     keycloak / multica / openmetadata / nifi / minio / minio-console"
echo "     (allemaal .odap.local). Pin per host."
echo "  3. Open https://platform.odap.local:8443/ — groene padlock."
