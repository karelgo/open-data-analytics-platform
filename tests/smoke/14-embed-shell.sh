#!/usr/bin/env bash
# Smoke test 14 — Portal embed-shell + path-routed services.
#
# Verifieert dat de unified iframe-shell van de portal correct werkt:
#   - elke /embed/<id>/-pagina is gebouwd (200 op de Astro static HTML)
#   - elk path-routed service-pad (/grafana, /prometheus, /airflow,
#     /superset, /jupyter) reageert via de portal-host
#   - elke subdomain-service stuurt de juiste CSP frame-ancestors mee
#   - Grafana stuurt geen X-Frame-Options: DENY meer
#
# Bewust geen OIDC-login — alleen pre-auth + header-checks. Eindgebruiker-
# flow (login → klik door /me → land in iframe) test je in de browser.
#
# Mode-aware: --mode=k3d|aks|stackit. K3d gebruikt :8443; cloud-modes 443.
set -euo pipefail

pass() { printf '\033[1;32m  OK\033[0m  %s\n' "$*"; }
fail() { printf '\033[1;31m  FAIL\033[0m %s\n' "$*" >&2; FAILED=1; }
skip() { printf '  [SKIP] %s\n' "$*"; }
log()  { printf '\033[1;34m  ==>\033[0m %s\n' "$*"; }

DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-${MODE:-k3d}}"
PLATFORM_DOMAIN="${PLATFORM_DOMAIN:-odap.local}"
case "$DEPLOYMENT_MODE" in
  k3d)             PORT_SUFFIX=":8443" ;;
  aks|stackit|*)   PORT_SUFFIX="" ;;
esac

# Cloud-modes hebben hun eigen TLD; values voor PLATFORM_DOMAIN worden
# door scripts/lib/mode.sh gezet (example.com /
# example.com). De TLD-rewrite in Layout.astro doet hetzelfde
# voor de browser; deze test gebruikt PLATFORM_DOMAIN direct.
PORTAL="https://platform.${PLATFORM_DOMAIN}${PORT_SUFFIX}"

FAILED=0

# ── 1. Embed-pagina HTML (oauth2-proxy gate → 302 of 200 met embed-frame).
log "1/4 Astro static /embed/<id>/ pagina's bereikbaar"
for id in grafana prometheus airflow superset jupyter openmetadata minio multica nanitics opensearch spark keycloak dbt-docs; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" "${PORTAL}/embed/${id}/")
  if [[ "$code" == "200" || "$code" == "302" ]]; then
    pass "/embed/${id}/ → HTTP $code"
  else
    fail "/embed/${id}/ → HTTP $code (verwacht 200 of 302)"
  fi
done

# ── 2. Path-routed services responderen onder portal-host.
log "2/4 path-routed services (same-origin onder /<svc>)"
# Format: "naam:pad" — bash 3.2-compat (geen associative arrays nodig).
# Superset zit hier NIET in: blueprint-prefix conflict (zie components.ts
# embed-comment) maakt path-routing onpraktisch — Superset draait via
# subdomain en wordt in stap 3 op CSP gecheckt.
for entry in \
  "grafana:/grafana/" \
  "prometheus:/prometheus/" \
  "airflow:/airflow/" \
  "jupyter:/jupyter/hub/login"; do
  svc="${entry%%:*}"
  path="${entry#*:}"
  code=$(curl -sk -o /dev/null -w "%{http_code}" "${PORTAL}${path}")
  # 200 = page served, 302 = login redirect (both are healthy).
  if [[ "$code" == "200" || "$code" == "302" ]]; then
    pass "${svc} (${path}) → HTTP $code"
  else
    fail "${svc} (${path}) → HTTP $code"
  fi
done

# ── 3. Subdomain services hebben iframe-allow CSP.
# keycloak hoort ook in deze lijst — z'n login-page wordt geiframed
# tijdens OAuth-redirects vanuit path-routed services (Airflow, Jupyter,
# Grafana) en moest daarom ook X-Frame-Options strippen + CSP
# frame-ancestors zetten.
log "3/4 subdomain services sturen frame-ancestors CSP"
for h in keycloak openmetadata minio-console multica nanitics opensearch spark superset; do
  csp=$(curl -sk -I "https://${h}.${PLATFORM_DOMAIN}${PORT_SUFFIX}/" 2>/dev/null \
    | grep -i "content-security-policy" | grep -i "frame-ancestors" || true)
  if [[ -n "$csp" ]] && echo "$csp" | grep -q "platform.${PLATFORM_DOMAIN}"; then
    pass "${h}: CSP frame-ancestors bevat platform.${PLATFORM_DOMAIN}"
  else
    # Spark + nanitics zijn cluster-conditional (driver moet draaien)
    if [[ "$h" == "spark" || "$h" == "nanitics" ]]; then
      skip "${h}: CSP niet gevonden (mogelijk geen pod draaiend)"
    else
      fail "${h}: CSP frame-ancestors ontbreekt of mismatcht"
    fi
  fi
done

# ── 4. Grafana stuurt geen X-Frame-Options: DENY (allow_embedding=true).
log "4/6 Grafana X-Frame-Options niet DENY"
xfo=$(curl -sk -I "${PORTAL}/grafana/" 2>/dev/null | grep -i "x-frame-options" || true)
if [[ -z "$xfo" ]] || ! echo "$xfo" | grep -qi "deny"; then
  pass "Grafana stuurt geen X-Frame-Options: DENY (${xfo:-geen header})"
else
  fail "Grafana stuurt nog X-Frame-Options: DENY — allow_embedding=true werkt niet"
fi

# ── 5. Airflow FAB CSS bereikbaar onder /airflow/auth/static/appbuilder/.
# Belangrijke regressie-check: zonder de aparte /airflow/auth ingress
# (X-Forwarded-Prefix=/airflow/auth) rendert FAB z'n bootstrap.css URL als
# /airflow/static/appbuilder/... wat 404't, en de hidden modal "User
# confirmation needed" wordt zichtbaar zonder styling.
log "5/6 Airflow FAB-rendered static assets onder /airflow/auth/static/"
fab_css_code=$(curl -sk -o /dev/null -w "%{http_code}" "${PORTAL}/airflow/auth/static/appbuilder/css/bootstrap.min.css")
if [[ "$fab_css_code" == "200" ]]; then
  pass "FAB bootstrap.min.css → HTTP $fab_css_code"
else
  fail "FAB bootstrap.min.css → HTTP $fab_css_code (verwacht 200)"
fi
# Login-pagina linkt naar /airflow/auth/static/... (correct prefix).
login_href=$(curl -sk "${PORTAL}/airflow/auth/login/" 2>/dev/null \
  | grep -oE "href=\"[^\"]+bootstrap\.min\.css\"" | head -1)
if echo "$login_href" | grep -q "/airflow/auth/static/"; then
  pass "FAB login-pagina linkt CSS naar /airflow/auth/static/ (juiste prefix)"
else
  fail "FAB login-pagina linkt CSS naar verkeerd pad: $login_href"
fi

# ── 6. Portal CSP heeft `font-src 'self' data:` voor dbt-docs.
# dbt-docs static-bundle bevat 3 inline data:font fonts. Zonder
# `data:` in font-src valt 'ie naar default-src 'self' → fonts geblokkeerd
# → page rendert ongestyleerd (geen icons, default typografie).
# Check direct op nginx in de pod omdat oauth2-proxy 302't en headers
# niet doorzet aan unauthenticated requests.
log "6/6 Portal CSP whitelist't data: in font-src (dbt-docs fonts)"
PORTAL_POD=$(kubectl -n odap-platform get pod -l app.kubernetes.io/name=portal \
  -o jsonpath="{.items[0].metadata.name}" 2>/dev/null)
if [[ -n "$PORTAL_POD" ]]; then
  font_src=$(kubectl -n odap-platform exec "$PORTAL_POD" -c portal-web -- \
    curl -sk -I "http://localhost:8080/dbt-docs.html" 2>/dev/null \
    | grep -i "content-security-policy" | grep -oE "font-src[^;]+" | head -1)
  if echo "$font_src" | grep -q "data:"; then
    pass "Portal CSP: $font_src"
  else
    fail "Portal CSP mist 'data:' in font-src: ${font_src:-(geen font-src directive)}"
  fi
else
  skip "Portal pod niet gevonden — CSP check overgeslagen"
fi

echo
if [[ $FAILED -eq 0 ]]; then
  printf '\033[1;32m  ✓ Smoke test 14 — embed-shell volledig in orde\033[0m\n'
  exit 0
else
  printf '\033[1;31m  ✗ Smoke test 14 — embed-shell heeft fouten\033[0m\n'
  exit 1
fi
