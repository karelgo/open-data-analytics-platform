#!/usr/bin/env bash
# scripts/azure/setup-acs-email-test.sh
#
# Finaliseert de Azure-Communication-Services-Email-setup voor de
# personal-Azure-test van de alert-pijp.
#
# Twee modi:
#
#   A) "CLI-modus" (Graph-access beschikbaar):
#      Script maakt zelf Entra-app + client-secret + role-assignment.
#      Required `az login --scope https://graph.microsoft.com//.default`.
#
#   B) "Portal-modus" (Graph-access geblokkeerd door Conditional Access):
#      Jij doet stappen 1-3 in de Azure-portal en geeft de client-ID +
#      secret-waarde mee als flag. Script slaat alle Graph-calls over.
#      Zie platform-overlays/azure-personal/14-monitoring/README.md.
#
# Beide modi:
#   4. Bouw SMTP-authUsername (formaat:
#        <acs-resource-name>.<entra-app-id>.<tenant-id>
#      — per MS Learn /azure/communication-services/concepts/email/
#      email-smtp-authentication-microsoft-entra).
#   5. Patch het k8s-Secret 'alertmanager-receivers' (odap-monitoring NS)
#      met smtp_password_acs = <client-secret>
#   6. Patch platform-overlays/azure-personal/14-monitoring/
#      alertmanager-add-acs.yaml with the authUsername.
#
# Voorbeeld portal-modus:
#   bash scripts/azure/setup-acs-email-test.sh \
#     --app-client-id 8a3f0c12-... \
#     --client-secret 'abc.123~xyz'
#
# Idempotent: bij her-runnen overschrijft het bestaande Secret-key +
# overlay-placeholder.

set -euo pipefail

SUBSCRIPTION_ID="4910a5a6-aec6-405d-9294-c7f2845512a4"
TENANT_ID="fedcef2f-0c85-40dd-8f55-e23143dcb367"
RG="dev-stackable-rg"
ACS_NAME="acs"
EMAIL_SERVICE_NAME="emailcs"
EMAIL_DOMAIN_NAME="AzureManagedDomain"
APP_DISPLAY_NAME="odap-platform-alertmanager-smtp"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OVERLAY_PATCH="${ROOT}/platform-overlays/azure-personal/14-monitoring/alertmanager-add-acs.yaml"

# --- helpers ---------------------------------------------------------
log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32mOK\033[0m  %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*"; }
die()  { printf '\033[1;31mFAIL\033[0m %s\n' "$*" >&2; exit 1; }

# --- arg parsing ------------------------------------------------------
APP_CLIENT_ID=""
CLIENT_SECRET=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-client-id)  APP_CLIENT_ID="$2"; shift 2 ;;
    --app-client-id=*) APP_CLIENT_ID="${1#*=}"; shift ;;
    --client-secret)  CLIENT_SECRET="$2"; shift 2 ;;
    --client-secret=*) CLIENT_SECRET="${1#*=}"; shift ;;
    -h|--help)
      sed -n '2,40p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) die "Onbekende flag: $1 (zie --help)" ;;
  esac
done

# Detect mode: portal-modus als BEIDE flags gegeven zijn.
PORTAL_MODE="no"
if [[ -n "$APP_CLIENT_ID" && -n "$CLIENT_SECRET" ]]; then
  PORTAL_MODE="yes"
elif [[ -n "$APP_CLIENT_ID" || -n "$CLIENT_SECRET" ]]; then
  die "Gebruik BEIDE --app-client-id en --client-secret samen, of geen van beide (voor CLI-modus)."
fi

for cmd in az kubectl jq python3; do
  command -v "$cmd" >/dev/null 2>&1 || die "vereist commando ontbreekt: $cmd"
done

# --- preflight: subscription ------------------------------------------
log "Set subscription"
az account set --subscription "$SUBSCRIPTION_ID"

# --- lookup ACS resource (ARM, geen Graph) ----------------------------
log "Lookup ACS resource"
ACS_JSON="$(az communication show --name "$ACS_NAME" --resource-group "$RG" -o json)"
ACS_ID="$(jq -r .id <<<"$ACS_JSON")"
ACS_IMMUTABLE_ID="$(jq -r .immutableResourceId <<<"$ACS_JSON")"
[[ -n "$ACS_ID" && "$ACS_ID" != "null" ]] || die "$ACS_NAME niet gevonden in $RG"

log "Lookup azure-managed sender domain"
DOMAIN_JSON="$(az communication email domain show \
  --domain-name "$EMAIL_DOMAIN_NAME" \
  --email-service-name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RG" -o json)"
SENDER_DOMAIN="$(jq -r .fromSenderDomain <<<"$DOMAIN_JSON")"
[[ -n "$SENDER_DOMAIN" && "$SENDER_DOMAIN" != "null" ]] || die "AzureManagedDomain niet gevonden in $EMAIL_SERVICE_NAME"
ok "Sender-domain: $SENDER_DOMAIN"
ok "Tenant ID:     $TENANT_ID"
ok "ACS resource:  $ACS_NAME"

# --- mode-A: CLI met Graph --------------------------------------------
if [[ "$PORTAL_MODE" == "no" ]]; then
  log "CLI-modus: test Graph-bereikbaarheid"
  if ! az ad signed-in-user show -o none 2>/dev/null; then
    cat <<EOF >&2
$(warn "Microsoft Graph wordt geblokkeerd door Conditional Access.")

Twee opties:

  Optie 1 — interactief opnieuw sign in (vereist browser-MFA):
      az login --scope https://graph.microsoft.com//.default
    en run dit script opnieuw zonder argumenten.

  Optie 2 — portal-modus (volg de stappen in
            platform-overlays/azure-personal/14-monitoring/README.md):
      bash scripts/azure/setup-acs-email-test.sh \\
        --app-client-id <PORTAL_VALUE> \\
        --client-secret '<PORTAL_VALUE>'
EOF
    exit 1
  fi
  ok "Graph bereikbaar"

  log "Find or create Entra-app '$APP_DISPLAY_NAME'"
  APP_CLIENT_ID="$(az ad app list --display-name "$APP_DISPLAY_NAME" \
    --query '[0].appId' -o tsv 2>/dev/null || true)"
  if [[ -z "$APP_CLIENT_ID" || "$APP_CLIENT_ID" == "None" ]]; then
    APP_CLIENT_ID="$(az ad app create \
      --display-name "$APP_DISPLAY_NAME" \
      --sign-in-audience AzureADMyOrg \
      --query 'appId' -o tsv)"
  fi
  ok "App client-ID: $APP_CLIENT_ID"

  log "Ensure service principal"
  SP_OBJECT_ID="$(az ad sp list --filter "appId eq '$APP_CLIENT_ID'" \
    --query '[0].id' -o tsv 2>/dev/null || true)"
  if [[ -z "$SP_OBJECT_ID" || "$SP_OBJECT_ID" == "None" ]]; then
    SP_OBJECT_ID="$(az ad sp create --id "$APP_CLIENT_ID" --query 'id' -o tsv)"
  fi
  ok "SP object-ID: $SP_OBJECT_ID"

  log "Generate client secret (rolls existing)"
  CLIENT_SECRET="$(az ad app credential reset \
    --id "$APP_CLIENT_ID" \
    --display-name "alertmanager-smtp" \
    --years 1 \
    --append false \
    --query 'password' -o tsv)"
  [[ -n "$CLIENT_SECRET" ]] || die "geen client-secret ontvangen"
  ok "Client-secret gegenereerd (lengte ${#CLIENT_SECRET})"

  log "Grant Contributor on $ACS_NAME"
  if [[ "$(az role assignment list --assignee-object-id "$SP_OBJECT_ID" \
        --scope "$ACS_ID" --role Contributor \
        --query 'length([])' -o tsv 2>/dev/null || echo 0)" == "0" ]]; then
    for attempt in 1 2 3 4 5; do
      if az role assignment create \
          --assignee-object-id "$SP_OBJECT_ID" \
          --assignee-principal-type ServicePrincipal \
          --role Contributor \
          --scope "$ACS_ID" >/dev/null 2>&1; then
        ok "Role assigned (attempt $attempt)"; break
      fi
      warn "Role-assign attempt $attempt mislukt — wacht 5s"
      sleep 5
      [[ "$attempt" == "5" ]] && die "Role-assign keer op keer mislukt"
    done
  else
    ok "Role-assignment bestaat al"
  fi

else
  # --- mode-B: portal --------------------------------------------------
  log "Portal-modus — sla Graph-stappen over (app/secret/role door jou in portal gedaan)"
  ok "App client-ID:    $APP_CLIENT_ID"
  ok "Client-secret:    (lengte ${#CLIENT_SECRET}, niet getoond)"
  warn "Verifieer in de portal dat de rol Contributor op $ACS_NAME is toegekend aan de service principal van $APP_DISPLAY_NAME."
fi

# --- compose SMTP authUsername ---------------------------------------
# Microsoft Entra ID auth voor ACS Email SMTP:
#   USER = <ACS-resource-name>.<Application-Id>.<Tenant-Id>   (dot-separated)
#   PASS = <client-secret>
SMTP_USERNAME="${ACS_NAME}.${APP_CLIENT_ID}.${TENANT_ID}"
log "SMTP username: $SMTP_USERNAME"

# --- patch overlay file ----------------------------------------------
log "Patch overlay-bestand"
[[ -f "$OVERLAY_PATCH" ]] || die "$OVERLAY_PATCH ontbreekt"
python3 - "$OVERLAY_PATCH" "$SMTP_USERNAME" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text()
new = re.sub(
    r'^(\s*authUsername:\s*).*$',
    rf'\1"{sys.argv[2]}"',
    text,
    count=1,
    flags=re.MULTILINE,
)
p.write_text(new)
PY
ok "Overlay-bestand bijgewerkt"

# --- patch k8s Secret ------------------------------------------------
log "Patch k8s Secret alertmanager-receivers"
if ! kubectl -n odap-monitoring get secret alertmanager-receivers >/dev/null 2>&1; then
  warn "Secret alertmanager-receivers bestaat nog niet in odap-monitoring."
  warn "Doe eerst 'make deploy MODE=k3d' (of apply platform/14-monitoring) en run opnieuw."
  exit 1
fi
B64="$(printf %s "$CLIENT_SECRET" | base64)"
kubectl -n odap-monitoring patch secret alertmanager-receivers \
  --type='json' \
  -p='[{"op":"add","path":"/data/smtp_password_acs","value":"'"$B64"'"}]' >/dev/null
ok "Secret-key smtp_password_acs gezet"

echo
cat <<EOF
=== Klaar ===

Apply de overlay en stuur een test-alert:
  kubectl apply -k platform-overlays/azure-personal/14-monitoring/
  make alert-test

Verwacht binnen ~30s:
  - MailHog UI:           https://mailhog.odap.local:8443/
  - Echte inbox:          karel.goense@freshminds.nl
    (subject: '[ACS-test FIRING] SyntheticTestAlert (warning)')

Bij SMTP-fouten:
  kubectl -n odap-monitoring logs -l app.kubernetes.io/name=alertmanager \\
    --tail=200 | grep -iE 'smtp|tls|auth'
EOF
