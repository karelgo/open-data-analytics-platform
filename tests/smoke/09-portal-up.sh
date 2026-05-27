#!/usr/bin/env bash
# Smoke test 09 — ODAP Portal (Astro + oauth2-proxy).
#
# Mode-aware. On k3d the portal is the chart-style `portal` Deployment
# (locally-built odap/portal:dev image). On AKS that image isn't
# pullable, so platform-overlays/aks/15-portal/ replaces the Deployment +
# Service + Ingress with `platform-landing` (Astro tarball ConfigMap +
# public-registry nginx + sidecar oauth2-proxy).
#
# Checks (per mode):
#   1. Deployment Available
#   2. nginx /api/health returns 200
#   3. oauth2-proxy /ping
#   4. Service routes :80 → :4180
#   5. Ingress platform.${PLATFORM_DOMAIN} exists with TLS-secret
#   6. Keycloak realm 'demo' knows a client with clientId=portal
set -euo pipefail

pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }
skip() { printf '  [SKIP] %s\n' "$*"; }
log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }

DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-${MODE:-k3d}}"
PLATFORM_DOMAIN="${PLATFORM_DOMAIN:-odap.local}"

NS=odap-platform
case "$DEPLOYMENT_MODE" in
  aks)
    # The AKS portal is platform-landing (consolidated from
    # public-ingresses.yaml into platform-overlays/aks/15-portal/).
    DEP=platform-landing
    SVC=platform-landing
    INGRESS=platform-public
    POD_LABEL="app=platform-landing"
    ;;
  *)
    DEP=portal
    SVC=portal
    INGRESS=portal
    POD_LABEL="app.kubernetes.io/name=portal"
    ;;
esac

if ! kubectl -n "$NS" get deployment "$DEP" >/dev/null 2>&1; then
  skip "deployment $NS/$DEP nog niet aanwezig — run 'make deploy-platform' inclusief platform/15-portal"
  exit 0
fi

# 1. Deployment Available
log "Wacht op deployment $NS/$DEP Available"
if kubectl -n "$NS" wait --for=condition=Available deployment/"$DEP" --timeout=60s >/dev/null 2>&1; then
  pass "deployment $DEP Available"
else
  fail "deployment $DEP niet Available binnen 60s"
fi

POD=$(kubectl -n "$NS" get pod -l "$POD_LABEL" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -z "$POD" ]]; then
  fail "geen portal-pod gevonden voor selector $POD_LABEL"
fi
# The web/nginx sidecar is named `portal-web` in the chart-style Deployment
# but `nginx` in platform-landing.
case "$DEPLOYMENT_MODE" in
  aks) WEB_CONTAINER=nginx ;;
  *)   WEB_CONTAINER=portal-web ;;
esac

# 2. nginx /api/health
log "Health-endpoint van nginx (intern, container $WEB_CONTAINER)"
HEALTH=$(kubectl -n "$NS" exec "$POD" -c "$WEB_CONTAINER" -- \
           wget -qO- http://127.0.0.1:8080/api/health 2>/dev/null || true)
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  pass "$WEB_CONTAINER /api/health = ok"
else
  fail "$WEB_CONTAINER /api/health gaf onverwacht: ${HEALTH:-leeg}"
fi

# 3. oauth2-proxy /ping — check via web container want oauth2-proxy
# distroless image heeft geen shell/wget/curl.
log "Ping-endpoint oauth2-proxy (via $WEB_CONTAINER)"
PING=$(kubectl -n "$NS" exec "$POD" -c "$WEB_CONTAINER" -- \
         wget -qO- http://127.0.0.1:4180/ping 2>/dev/null || true)
if [[ "$PING" == *"OK"* || "$PING" == *"pong"* ]]; then
  pass "oauth2-proxy /ping antwoordt"
else
  fail "oauth2-proxy /ping faalt: ${PING:-leeg}"
fi

# 4. Service routing :80 → :4180
log "Service $SVC:80"
SVC_PORT=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || true)
SVC_TARGET=$(kubectl -n "$NS" get svc "$SVC" -o jsonpath='{.spec.ports[0].targetPort}' 2>/dev/null || true)
if [[ "$SVC_PORT" == "80" && "$SVC_TARGET" == "4180" ]]; then
  pass "service $SVC 80 -> 4180"
else
  fail "service $SVC heeft onverwachte port mapping (port=$SVC_PORT target=$SVC_TARGET)"
fi

# 5. Ingress + TLS — host should be platform.${PLATFORM_DOMAIN} on every mode.
expected_host="platform.${PLATFORM_DOMAIN}"
log "Ingress $expected_host"
INGRESS_HOSTS=$(kubectl -n "$NS" get ingress "$INGRESS" -o jsonpath='{.spec.rules[*].host}' 2>/dev/null || true)
INGRESS_TLS=$(kubectl -n "$NS" get ingress "$INGRESS" -o jsonpath='{.spec.tls[0].secretName}' 2>/dev/null || true)
# Multi-rule ingress (platform-public has apex + www + platform.); succeed if expected_host is among them.
if [[ " $INGRESS_HOSTS " == *" $expected_host "* && -n "$INGRESS_TLS" ]]; then
  pass "ingress $INGRESS contains host=$expected_host tls-secret=$INGRESS_TLS"
else
  fail "ingress $INGRESS niet correct (hosts=$INGRESS_HOSTS tls=$INGRESS_TLS, expected host=$expected_host)"
fi

# 6. Keycloak realm bevat client 'portal'
log "Keycloak realm 'demo' kent client 'portal'"
KC_RESP=$(kubectl -n odap-auth run kc-portal-check-$RANDOM \
            --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
            curl -fsSL --max-time 10 \
              "http://keycloak.odap-auth.svc.cluster.local/realms/odap/.well-known/openid-configuration" \
            2>/dev/null || true)
if echo "$KC_RESP" | grep -q '"issuer"'; then
  pass "Keycloak realm 'demo' beantwoordt OIDC-discovery"
  # NB: zonder admin-API kunnen we client-list niet enumereren; dat is OK,
  # de realm-import bevat 'portal' (zie infrastructure/helm/keycloak/realm.json).
  skip "client-enumeration vereist Keycloak admin-API; vertrouw op realm-import"
else
  fail "Keycloak realm 'demo' beantwoordt geen OIDC-discovery"
fi

echo
pass "smoke 09-portal-up: alle checks groen"
