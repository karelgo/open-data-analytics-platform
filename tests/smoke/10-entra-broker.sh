#!/usr/bin/env bash
# Smoke test 10 — Entra ID brokering via Keycloak (feature/entra-id-broker).
#
# Checkt:
#   1. Realm 'uwv' beantwoordt OIDC-discovery (Keycloak draait).
#   2. Identity Provider 'entra' is geregistreerd in het realm
#      (zichtbaar via OIDC-discovery? nee — vereist admin-API of realm-export).
#      We controleren in plaats daarvan dat de realm-import-ConfigMap een
#      'entra'-IdP bevat (declaratieve evidence).
#   3. De Secret keycloak-entra-broker bestaat in odap-auth (placeholders OK).
#   4. Of de placeholders nog REPLACE_ME_* zijn — als ze ingevuld zijn,
#      additioneel: de Keycloak-loginpagina voor de portal-client toont
#      een knop "Microsoft Entra ID".
#
# Skipt elegant als Keycloak nog niet gedeployd is.
set -euo pipefail

pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }
warn() { printf '\033[1;33m  WARN\033[0m  %s\n' "$*"; }
skip() { printf '  [SKIP] %s\n' "$*"; }
log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }

KC_NS=odap-auth

# 0. Keycloak draait?
if ! kubectl -n "$KC_NS" get statefulset keycloak >/dev/null 2>&1 \
   && ! kubectl -n "$KC_NS" get deployment  keycloak >/dev/null 2>&1; then
  skip "Keycloak nog niet gedeployd in $KC_NS"
  exit 0
fi

# 1. OIDC-discovery
log "OIDC-discovery realm 'uwv'"
KC_RESP=$(kubectl -n "$KC_NS" run kc-discovery-$RANDOM \
            --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
            curl -fsSL --max-time 10 \
              "http://keycloak.odap-auth.svc.cluster.local/realms/odap/.well-known/openid-configuration" \
            2>/dev/null || true)
if echo "$KC_RESP" | grep -q '"issuer"'; then
  pass "realm 'uwv' beantwoordt OIDC-discovery"
else
  fail "realm 'uwv' OIDC-discovery faalt"
fi

# 2. ConfigMap keycloak-realm bevat IdP 'entra'
log "ConfigMap keycloak-realm bevat identityProvider 'entra'"
CM=$(kubectl -n "$KC_NS" get configmap keycloak-realm \
       -o jsonpath='{.data.realm\.json}' 2>/dev/null || true)
if [[ -z "$CM" ]]; then
  # fallback: filename kan ook anders heten — pak elke .json key
  CM=$(kubectl -n "$KC_NS" get configmap keycloak-realm -o json 2>/dev/null \
        | python3 -c 'import sys,json;d=json.load(sys.stdin)["data"];print(next(iter(d.values()),""))' \
        2>/dev/null || true)
fi
if [[ -z "$CM" ]]; then
  fail "ConfigMap keycloak-realm niet gevonden of leeg"
fi
if echo "$CM" | grep -q '"alias": *"entra"'; then
  pass "realm-import bevat IdP 'entra'"
else
  fail "realm-import bevat GEEN IdP 'entra' — feature niet correct gedeployd"
fi

# 3. Secret keycloak-entra-broker bestaat
log "Secret keycloak-entra-broker"
if kubectl -n "$KC_NS" get secret keycloak-entra-broker >/dev/null 2>&1; then
  pass "Secret keycloak-entra-broker aanwezig"
else
  fail "Secret keycloak-entra-broker ontbreekt in $KC_NS"
fi

# 4. Placeholder check
log "Placeholders in realm-import"
PLACEHOLDER_COUNT=$(echo "$CM" | grep -c 'REPLACE_ME_' || true)
if [[ "$PLACEHOLDER_COUNT" -gt 0 ]]; then
  warn "realm-import bevat nog $PLACEHOLDER_COUNT REPLACE_ME_* placeholders"
  warn "Entra-login werkt pas na invullen van tenantId, clientId, clientSecret en 11 group-GUIDs"
  warn "Zie platform/02-authentication/README.md → 'Entra ID brokering' voor de stappen"
  echo
  pass "smoke 10-entra-broker: structuur OK, configuratie nog onvolledig (verwacht in dev)"
  exit 0
fi
pass "geen REPLACE_ME_* placeholders meer — Entra is volledig geconfigureerd"

# 5. Loginpagina toont IdP-knop (alleen als config compleet is)
log "Keycloak-loginpagina toont 'Entra ID'-knop voor client portal"
LOGIN_HTML=$(kubectl -n "$KC_NS" run kc-login-$RANDOM \
              --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
              curl -fsSL --max-time 10 \
                "http://keycloak.odap-auth.svc.cluster.local/realms/odap/protocol/openid-connect/auth?client_id=portal&response_type=code&scope=openid&redirect_uri=https://platform.odap.local/oauth2/callback" \
              2>/dev/null || true)
if echo "$LOGIN_HTML" | grep -qi 'entra\|microsoft'; then
  pass "Loginpagina rendert Entra-knop"
else
  fail "Loginpagina rendert GEEN Entra-knop — IdP geconfigureerd maar niet zichtbaar?"
fi

echo
pass "smoke 10-entra-broker: alle checks groen"
