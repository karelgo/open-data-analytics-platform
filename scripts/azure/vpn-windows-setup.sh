#!/usr/bin/env bash
# Package the terraform-generated VPN client cert as a Windows-installable
# .pfx, fetch the Azure VPN profile zip, and print step-by-step Windows
# install instructions.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT/infrastructure/azure/terraform"
CERT_DIR="$ROOT/infrastructure/azure/vpn-client"

log()   { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
error() { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

# Sanity
[[ -f "$CERT_DIR/client.crt" && -f "$CERT_DIR/client.key" && -f "$CERT_DIR/root.crt" ]] \
  || error "Cert files missing under $CERT_DIR — run 'make aks-up' first."

# 1. Build PFX (cert + key + chain) for Windows cert store import.
PFX="$CERT_DIR/odap-platform-vpn-client.pfx"
PFX_PW="${PFX_PW:-uwv}"
log "Bundling client.crt + client.key + root.crt into $PFX (password: $PFX_PW)"
openssl pkcs12 -export \
  -out "$PFX" \
  -inkey "$CERT_DIR/client.key" \
  -in "$CERT_DIR/client.crt" \
  -certfile "$CERT_DIR/root.crt" \
  -name "Platform VPN Client" \
  -passout "pass:$PFX_PW" \
  >/dev/null 2>&1
chmod 600 "$PFX"

# 2. Fetch the Azure VPN client config zip (.exe profile installer for SSTP/IKEv2).
[[ -f "$ROOT/scripts/azure/env.sh" ]] && source "$ROOT/scripts/azure/env.sh"
GW_NAME=$(cd "$TF_DIR" && terraform output -raw vpn_gateway_name 2>/dev/null || true)
RG=$(cd "$TF_DIR" && terraform output -raw resource_group 2>/dev/null || echo dev-stackable-rg)

if [[ -n "$GW_NAME" ]]; then
  log "Fetching Azure VPN profile (Windows .exe configurer)"
  ZIP="$CERT_DIR/azure-vpn-profile.zip"
  PROFILE_URL=$(az network vnet-gateway vpn-client generate -g "$RG" -n "$GW_NAME" --processor-architecture Amd64 -o tsv 2>/dev/null || true)
  if [[ -n "$PROFILE_URL" ]]; then
    curl -fsSL "$PROFILE_URL" -o "$ZIP"
    log "Saved profile to $ZIP — unzip and run WindowsAmd64\\\\VpnClientSetupAmd64.exe on your Windows box"
  else
    log "(skip) Could not generate VPN profile yet — gateway may still be provisioning. Re-run later."
  fi
fi

# 3. Print instructions
GW_IP=$(cd "$TF_DIR" && terraform output -raw vpn_gateway_public_ip 2>/dev/null || echo "<provisioning>")
AKS_VNET=$(cd "$TF_DIR" && terraform output -json aks_vnet_address_space 2>/dev/null || echo "[]")
LB_INTERNAL=$(kubectl --context odap-platform-aks -n ingress-nginx get svc ingress-nginx-controller-internal -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "<not yet allocated>")

cat <<EOF

  ================================================================
   Platform VPN — Windows install
  ================================================================

   1. Copy these two files to your Windows machine:
        $PFX
        $CERT_DIR/azure-vpn-profile.zip   (if downloaded)

   2. On Windows, double-click the .pfx — Certificate Import Wizard:
        Store Location: Current User
        Password:       $PFX_PW
        Place all certs in: Personal

   3. Unzip azure-vpn-profile.zip and run WindowsAmd64\\VpnClientSetupAmd64.exe.
      A new VPN connection appears in Windows Settings.

   4. Connect: Settings → Network & Internet → VPN → "${GW_NAME:-<gw>}" → Connect.

   5. Once connected, edit C:\\Windows\\System32\\drivers\\etc\\hosts (admin):
        $LB_INTERNAL platform.odap-platform.cloud keycloak.odap-platform.cloud minio-console.odap-platform.cloud minio.odap-platform.cloud grafana.odap-platform.cloud openmetadata.odap-platform.cloud

      Then browse to https://platform.odap-platform.cloud — standard port 443,
      TLS via the platform's self-signed CA (browser will warn — accept once).

  Reference values (from terraform output):
    VPN Gateway IP   : $GW_IP
    AKS VNet         : $AKS_VNET
    Internal LB IP   : $LB_INTERNAL

EOF
