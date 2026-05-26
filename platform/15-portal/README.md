# platform/15-portal — ODAP Portal

Rol-aware launchpad + architectuurkaart + UDP Academy (certificeringstracks),
bereikbaar op **`https://platform.odap.local`** na `make deploy-platform`.

## UDP Academy

De `/learn/`-routes vormen het certificeringsplatform met 33 modules
(11 rollen × 3 levels) en SVG-certificaten. Alles is statisch behalve:

- voortgang sync via `/api/learn/progress` → Keycloak user-attribute
  `udp_progress` (Academy-backend deployment in [academy-backend.yaml](academy-backend.yaml));
- auto-checks via `/api/learn/check/<id>`.

Zonder de backend werkt alles op localStorage; voortgang is dan per browser.

### Keycloak service-account

De backend praat met Keycloak admin-API via `client_id=portal-backend`
(zie [realm.json](../../infrastructure/helm/keycloak/realm.json)).

Eenmalig na realm-import: ken `realm-management:manage-users` toe aan het
service-account user:

```bash
kcadm.sh add-roles \
  -r uwv \
  --uusername service-account-portal-backend \
  --cclientid realm-management \
  --rolename manage-users
```

Daarna kan de backend voortgang naar user-attributes schrijven.

## Architectuur

```
Browser ── ingress-nginx ──► Service portal:80
                              │
                              ▼ targetPort 4180
                        ┌─────────────────────┐
                        │  Pod: portal        │
                        │  ┌───────────────┐  │
                        │  │ oauth2-proxy  │  │  :4180
                        │  │  (sidecar)    │  │
                        │  └───────┬───────┘  │
                        │          │ upstream │
                        │          ▼          │
                        │  ┌───────────────┐  │
                        │  │ nginx-static  │  │  :8080
                        │  │  (Astro dist) │  │  /api/health
                        │  │  /api/status  │──┼──► Prometheus
                        │  └───────────────┘  │
                        └─────────────────────┘
                              │
                              ▼  OIDC redirect/redeem
                       Keycloak realm 'uwv'
```

- **oauth2-proxy** ([`configmap-oauth2-proxy.yaml`](configmap-oauth2-proxy.yaml))
  praat met Keycloak via een _split-URL-patroon_:
  - `oidc_issuer_url` is de **externe** URL (`https://keycloak.odap.local`)
    omdat Keycloak met `proxy: edge` + `hostname: keycloak.odap.local`
    draait — issuer-claim in tokens is altijd de externe URL.
  - `redeem_url`, `profile_url`, `oidc_jwks_url` zijn de **in-cluster** URL
    (`http://keycloak.odap-auth.svc.cluster.local`) zodat de pod ze kan bereiken
    zonder `keycloak.odap.local` te hoeven resolveren.
- **nginx-unprivileged** serveert de Astro-dist op `:8080` en proxy't
  `/api/status/up?job=…` door naar `prometheus-server.odap-monitoring.svc`
  voor de live status-badges.
- **Realm-client `portal`** wordt gedeployd via
  [`infrastructure/helm/keycloak/realm.json`](../../infrastructure/helm/keycloak/realm.json).
  Secrets staan in [`secret.yaml`](secret.yaml) (DEV-ONLY).

## Image bouwen

```bash
# vanuit repo-root
docker build -f portal/Dockerfile -t odap/portal:dev .
# Cluster-naam = $CLUSTER_NAME uit Makefile (default: odap-platform).
k3d image import odap/portal:dev -c odap-platform
```

## Smoke

```bash
bash tests/smoke/09-portal-up.sh
```

## Bron-code

Astro-bron staat in [`portal/`](../../portal/).
