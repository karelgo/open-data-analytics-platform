#!/usr/bin/env bash
# Smoke test 12 — ODAP Lab (JupyterHub).
#
# Checkt:
#   1. Deployment `jupyterhub` is Available
#   2. Hub /hub/health antwoordt 200
#   3. configurable-http-proxy luistert op :8000
#   4. Service `jupyter` mapt 80 → 8000
#   5. Service `hub` mapt 8081 → 8081
#   6. Ingress jupyter.odap.local bestaat met TLS-secret
#   7. ConfigMap `jupyterhub-config` bevat de oauthenticator-config
#   8. ConfigMap `jupyter-starter-notebooks` bestaat met >=5 notebooks
#   9. Singleuser ServiceAccount + Role + RoleBinding aanwezig
#  10. Keycloak realm 'demo' OIDC-discovery werkt (sanity, niet client-enum)
#  11. odap_lab Python-helper importeert in een kernel-test-pod
#
# Skipt elegant als JupyterHub nog niet gedeployd is.
set -euo pipefail

pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; exit 1; }
skip() { printf '  [SKIP] %s\n' "$*"; }
log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }

DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-${MODE:-k3d}}"
PLATFORM_DOMAIN="${PLATFORM_DOMAIN:-odap.local}"

NS=odap-platform
DEP=jupyterhub

if ! kubectl -n "$NS" get deployment "$DEP" >/dev/null 2>&1; then
  skip "deployment $NS/$DEP nog niet aanwezig — run 'make deploy-platform' inclusief platform/16-jupyter"
  exit 0
fi

# 1. Deployment Available
log "Wacht op deployment $NS/$DEP Available"
if kubectl -n "$NS" wait --for=condition=Available deployment/"$DEP" --timeout=180s >/dev/null 2>&1; then
  pass "deployment $DEP Available"
else
  fail "deployment $DEP niet Available binnen 180s"
fi

POD=$(kubectl -n "$NS" get pod -l app.kubernetes.io/name=jupyterhub,app.kubernetes.io/component=hub \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -z "$POD" ]]; then
  fail "geen jupyterhub-pod gevonden"
fi

# 2. Hub health (internal)
log "Hub /hub/health (intern, container hub)"
HEALTH_CODE=$(kubectl -n "$NS" exec "$POD" -c hub -- \
                python -c "import urllib.request as u, json; r=u.urlopen('http://127.0.0.1:8081/hub/health', timeout=5); print(r.status)" \
                2>/dev/null || true)
if [[ "$HEALTH_CODE" == "200" ]]; then
  pass "Hub /hub/health = 200"
else
  fail "Hub /hub/health gaf onverwacht: ${HEALTH_CODE:-leeg}"
fi

# 3. configurable-http-proxy /api/v1 (root proxies to Hub which 302s to /hub/login)
log "configurable-http-proxy proxy-target 200/302 (port 8000)"
PROXY_CODE=$(kubectl -n "$NS" exec "$POD" -c hub -- \
               python -c "import urllib.request as u; r=u.urlopen('http://127.0.0.1:8000', timeout=5); print(r.status)" \
               2>/dev/null || true)
if [[ "$PROXY_CODE" =~ ^(200|302)$ ]]; then
  pass "proxy :8000 actief (status=$PROXY_CODE)"
else
  fail "proxy :8000 reageert niet (status=${PROXY_CODE:-leeg})"
fi

# 4. Service jupyter routing
log "Service jupyter:80 → :8000"
J_PORT=$(kubectl -n "$NS" get svc jupyter -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || true)
J_TARGET=$(kubectl -n "$NS" get svc jupyter -o jsonpath='{.spec.ports[0].targetPort}' 2>/dev/null || true)
if [[ "$J_PORT" == "80" && "$J_TARGET" == "8000" ]]; then
  pass "service jupyter 80 -> 8000"
else
  fail "service jupyter port-mapping fout (port=$J_PORT target=$J_TARGET)"
fi

# 5. Service hub (internal API)
log "Service hub:8081"
H_PORT=$(kubectl -n "$NS" get svc hub -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || true)
if [[ "$H_PORT" == "8081" ]]; then
  pass "service hub 8081 aanwezig"
else
  fail "service hub niet correct (port=$H_PORT)"
fi

# 6. Ingress + TLS
expected_host="jupyter.${PLATFORM_DOMAIN}"
log "Ingress $expected_host"
J_HOST=$(kubectl -n "$NS" get ingress jupyter -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || true)
J_TLS=$(kubectl -n "$NS" get ingress jupyter -o jsonpath='{.spec.tls[0].secretName}' 2>/dev/null || true)
if [[ "$J_HOST" == "$expected_host" && -n "$J_TLS" ]]; then
  pass "ingress host=$J_HOST tls-secret=$J_TLS"
else
  fail "ingress jupyter niet correct (host=$J_HOST tls=$J_TLS, expected host=$expected_host)"
fi

# 7. ConfigMap jupyterhub-config
log "ConfigMap jupyterhub-config bevat OAuthenticator-config"
if kubectl -n "$NS" get configmap jupyterhub-config -o jsonpath='{.data.jupyterhub_config\.py}' 2>/dev/null \
     | grep -q 'GenericOAuthenticator'; then
  pass "jupyterhub-config bevat GenericOAuthenticator-regel"
else
  fail "jupyterhub-config mist OAuthenticator-config"
fi

# 8. Starter-notebooks ConfigMap
log "ConfigMap jupyter-starter-notebooks bevat >=5 notebooks"
NB_COUNT=$(kubectl -n "$NS" get configmap jupyter-starter-notebooks \
             -o go-template='{{len .data}}' 2>/dev/null || echo 0)
if [[ "$NB_COUNT" -ge 5 ]]; then
  pass "starter-notebooks ConfigMap aanwezig ($NB_COUNT notebooks)"
else
  fail "starter-notebooks ConfigMap te klein of ontbreekt (count=$NB_COUNT)"
fi

# 9. Singleuser ServiceAccount + Role + RoleBinding
log "Singleuser ServiceAccount + Hub-Role aanwezig"
kubectl -n "$NS" get sa jupyterhub-singleuser >/dev/null 2>&1 || fail "ServiceAccount jupyterhub-singleuser ontbreekt"
kubectl -n "$NS" get sa jupyterhub             >/dev/null 2>&1 || fail "ServiceAccount jupyterhub ontbreekt"
kubectl -n "$NS" get role jupyterhub           >/dev/null 2>&1 || fail "Role jupyterhub ontbreekt"
kubectl -n "$NS" get rolebinding jupyterhub    >/dev/null 2>&1 || fail "RoleBinding jupyterhub ontbreekt"
pass "RBAC voor Hub + singleuser correct opgezet"

# 10. Keycloak realm answers OIDC discovery (sanity)
log "Keycloak realm 'demo' OIDC-discovery"
KC=$(kubectl -n odap-auth run kc-jupyter-check-$RANDOM \
       --image=curlimages/curl:8.10.1 --rm -i --restart=Never --quiet -- \
       curl -fsSL --max-time 10 \
         "http://keycloak.odap-auth.svc.cluster.local/realms/odap/.well-known/openid-configuration" \
       2>/dev/null || true)
if echo "$KC" | grep -q '"issuer"'; then
  pass "Keycloak realm 'demo' OIDC-discovery werkt"
else
  fail "Keycloak realm 'demo' beantwoordt geen OIDC-discovery"
fi

# 11. odap_lab helper importeert in een kernel-test-pod (lichtgewicht — pod
#     runt python -c en sluit weer af).
#
# Op AKS is `odap/jupyter-kernel:dev` niet pullable zonder dat het
# image naar een registry is gepusht (geen `k3d image import` beschikbaar).
# Sla de check over tot er een registry-push-flow is.
if [[ "$DEPLOYMENT_MODE" == "aks" ]]; then
  skip "odap_lab kernel-import — kernel-image staat niet op een registry die AKS kan pullen (TODO: ACR-push)"
else
  log "odap_lab helper import in kernel-image"
  if kubectl -n "$NS" get pod kernel-smoketest >/dev/null 2>&1; then
    kubectl -n "$NS" delete pod kernel-smoketest --ignore-not-found >/dev/null 2>&1 || true
  fi
  IMG=$(kubectl -n "$NS" get deployment "$DEP" -o jsonpath='{.spec.template.spec.containers[?(@.name=="hub")].env[?(@.name=="SINGLEUSER_IMAGE")].value}')
  [[ -z "$IMG" ]] && IMG="odap/jupyter-kernel:dev"
  KERNEL_OUT=$(kubectl -n "$NS" run kernel-smoketest \
                 --image="$IMG" --image-pull-policy=IfNotPresent \
                 --restart=Never --rm -i --quiet --command -- \
                 python -c "import odap_lab; print('odap_lab', 'OK', list(odap_lab.env().keys())[:3])" \
                 2>/dev/null || true)
  if echo "$KERNEL_OUT" | grep -q "odap_lab OK"; then
    pass "kernel-image kan 'import odap_lab' (output: $KERNEL_OUT)"
  else
    fail "kernel-image kon 'odap_lab' niet importeren — image-build of import-error. Output: ${KERNEL_OUT:-leeg}"
  fi
fi

echo
pass "smoke 12-jupyter-up: alle checks groen"
