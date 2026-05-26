# ODAP Portal (Astro)

Rol-aware launchpad + klikbare reference-architectuur voor het UWV Referentie
Data- en Analyseplatform.

Deze portal is een **statische site** (Astro build → nginx) met:

- **Home** (`/`) — overzicht van het platform met de reference-architectuur
  (Monte-Carlo-stijl) als landing.
- **Architectuur** (`/architecture`) — visuele reference-architectuur met
  brand-iconen per component, lanes voor Discovery / Pipeline / Observability,
  en gegroepeerde componenten per stage met zoekfilter. Status-stippen tonen
  live `up{job=…}` uit Prometheus.
- **Mijn werkplek** (`/me`) — leest de Keycloak-rol uit het OIDC-token (via
  `oauth2-proxy`) en toont alleen de tools, catalogs en shortcuts die bij die
  rol horen. De reference-architectuur op deze pagina markeert "jouw"
  componenten.

Donker thema standaard, licht-thema-toggle in de topbar (voorkeur in
`localStorage`).

Geen JavaScript-framework, geen Node-runtime in productie. SSO via een
sidecar `oauth2-proxy` voor de nginx-container.

## Lokale development

```bash
cd portal
npm install
npm run dev
# open http://localhost:4321
```

In dev draait Astro zonder `oauth2-proxy`; `/me` valt terug op een
demo-modus (`/me?role=wia_beoordelaar`). Status-badges blijven grijs omdat
er geen Prometheus-proxy beschikbaar is.

## Datastromen

Eén bron van waarheid:

| Wat | Bron | Hoe |
|---|---|---|
| Rol-capabilities | [`opa-policies-src/data/role_mappings.json`](../opa-policies-src/data/role_mappings.json) | `scripts/sync-data.mjs` kopieert naar `src/data/role-mappings.generated.json` vóór build |
| Component-URLs + beschrijvingen + iconen + stages | [`src/data/components.ts`](src/data/components.ts) | handmatig (single-source binnen portal); brand-iconen in [`public/icons/brand/`](public/icons/brand) en stage-iconen in [`public/icons/stage/`](public/icons/stage) |
| Per-rol shortcuts | [`src/data/role-shortcuts.ts`](src/data/role-shortcuts.ts) | handmatig, gebaseerd op [`docs/handleidingen`](../docs/handleidingen) |
| Live status | Prometheus, via `/api/status/up?job=…` | nginx proxy_pass naar `prometheus.odap-monitoring.svc.cluster.local` |

## Productie-deployment

Zie [`platform/15-portal/`](../platform/15-portal/) — Kubernetes manifests
(Deployment met `oauth2-proxy` sidecar + nginx, Service, Ingress).
Container-image: `odap/portal` (build via [`Dockerfile`](Dockerfile)).
