// Centrale registry van platform-componenten.
// Enige plek waar URLs, beschrijvingen en welke rollen welke component
// gebruiken bij elkaar staan. Wordt gelezen door architectuur-diagram,
// rol-werkplek en status-badges.

export type ComponentId =
  | 'keycloak'
  | 'minio'
  | 'hive'
  | 'kafka'
  | 'nifi'
  | 'spark'
  | 'trino'
  | 'opa'
  | 'airflow'
  | 'superset'
  | 'powerbi'
  | 'openmetadata'
  | 'dbt-docs'
  | 'jupyter'
  | 'prometheus'
  | 'grafana'
  | 'opensearch'
  | 'multica'
  | 'nanitics';

// Legacy "layer" — fijne granulariteit voor de oude card-tag.
export type ComponentLayer =
  | 'auth'
  | 'storage'
  | 'metadata'
  | 'streaming'
  | 'compute'
  | 'query'
  | 'policy'
  | 'orchestration'
  | 'bi'
  | 'governance'
  | 'observability'
  | 'ai-agents';

// Reference-architecture lanes (Monte-Carlo-stijl).
// Hier groeperen we componenten in de plek die ze in de pipeline innemen.
export type ComponentStage =
  | 'sources'
  | 'ingestion'
  | 'storage'
  | 'transformation'
  | 'consumption'
  | 'discovery'
  | 'pipeline'
  | 'observability'
  | 'identity'
  | 'agents';

// Embed-config — bepaalt of een component in de portal-shell (iframe) past,
// en welke URL we als iframe.src gebruiken. Apart van `url` zodat het
// "open in nieuw tabblad"-gedrag (en de TLD-rewrite in Layout.astro) blijft
// werken met de oorspronkelijke externe URL.
//
// - 'subpath':   de service draait onder platform.odap.local/<path>/
//                (same-origin, geen cross-origin cookie-issues).
// - 'subdomain': service draait op een eigen <svc>.<tld> en wordt cross-origin
//                geiframed. Vereist dat de service X-Frame-Options/CSP toestaat
//                en cookies SameSite=None;Secure heeft.
// - 'none':      niet iframe-baar (Keycloak login, MinIO S3-API, …).
//                Link altijd in nieuw tabblad.
export type EmbedMode = 'subpath' | 'subdomain' | 'none';

export interface EmbedConfig {
  mode: EmbedMode;
  // Voor 'subpath': pad onder de portal-host (begin met '/').
  // Voor 'subdomain': leeg laten — we gebruiken `url` als basis.
  path?: string;
  // Override de iframe-src base. Nuttig als `url` naar een portal-pagina
  // wijst (bv. MinIO's /go/minio/ SSO-bootstrap) maar de iframe gewoon
  // direct naar het service-subdomein moet. Layout-chrome in een iframe
  // is verwarrend; betere UX is direct laden.
  iframeBase?: string;
}

export interface PlatformComponent {
  id: ComponentId;
  name: string;
  layer: ComponentLayer;
  stage: ComponentStage;
  short: string;
  purpose: string;
  icon: string;
  url: string | null;
  embed?: EmbedConfig;
  prometheusJob?: string;
  rolesUsing: string[];
}

export const components: PlatformComponent[] = [
  {
    id: 'keycloak',
    name: 'Keycloak',
    layer: 'auth',
    stage: 'identity',
    short: 'OIDC-identity provider — single sign-on en MFA voor alle componenten.',
    purpose: 'Eén keer inloggen, overal toegang volgens je rol. MFA en audit-log centraal.',
    icon: '/icons/brand/keycloak.svg',
    url: 'https://keycloak.odap.local:8443',
    // Keycloak admin-console is bewust niet iframe-baar — login-redirects
    // breken in iframe-context, en sommige browsers blokkeren third-party
    // OIDC-cookies sowieso. Open altijd in een nieuw tabblad.
    embed: { mode: 'none' },
    prometheusJob: 'keycloak',
    rolesUsing: ['*'],
  },
  {
    id: 'nifi',
    name: 'Apache NiFi',
    layer: 'streaming',
    stage: 'ingestion',
    short: 'Visuele ingestion-flows — bronsystemen → Kafka.',
    purpose: 'Data uit UWV-bronsystemen ophalen en in het platform binnenbrengen.',
    icon: '/icons/brand/nifi.svg',
    // Flows worden as-code beheerd (process-group JSON, REST-import); de UI
    // is geen onderdeel van de dagelijkse workflow. Geen klikbare link op /me.
    url: null,
    embed: { mode: 'none' },
    prometheusJob: 'nifi',
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
  {
    id: 'kafka',
    name: 'Kafka',
    layer: 'streaming',
    stage: 'ingestion',
    short: 'Event-bus tussen NiFi-ingestion en Spark Structured Streaming.',
    purpose: 'Data-events bufferen en doorzetten naar verwerking. Schaalbare doorvoer.',
    icon: '/icons/brand/kafka.svg',
    url: null,
    embed: { mode: 'none' },
    prometheusJob: 'kafka',
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
  {
    id: 'minio',
    name: 'MinIO',
    layer: 'storage',
    stage: 'storage',
    short: 'S3-compatible object store met buckets bronze/silver/gold/sensitive.',
    purpose: 'Het lakehouse waar alle data fysiek staat — gelaagd in zones met aparte toegangsregels.',
    icon: '/icons/brand/minio.svg',
    // /go/minio/ — minimale iframe-bootstrap die de Keycloak SSO-flow
    // start (via portal-nginx in-cluster proxy naar de MinIO Console
    // /api/v1/login). MinIO Console's externe /api/v1/login retourneert
    // `redirectRules: null` (Console-quirk), maar de in-cluster Service
    // wél — dus we proxyen die ene endpoint via portal/nginx.conf
    // (/api/minio-sso/login). Zonder dit zou de embed-iframe alleen
    // het form-login scherm tonen i.p.v. direct in te loggen via SSO.
    url: '/go/minio/',
    // iframeBase = /go/minio/: de iframe laadt onze bootstrap-page die
    // synchroon door-302't naar Keycloak SSO. Geen flashing portal-chrome
    // — bootstrap-page heeft alleen een spinner. Eindresultaat: user
    // landt direct op de MinIO Console UI ingelogd, zonder klik.
    embed: {
      mode: 'subdomain',
      iframeBase: '/go/minio/',
    },
    prometheusJob: 'minio',
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
  {
    id: 'hive',
    name: 'Hive Metastore',
    layer: 'metadata',
    stage: 'storage',
    short: 'Catalog backend — houdt tabel-schemas en partities bij voor Trino en Spark.',
    purpose: 'Vertaalt bestanden in MinIO naar tabellen met kolommen en types.',
    icon: '/icons/brand/hive.svg',
    url: null,
    embed: { mode: 'none' },
    prometheusJob: 'hive',
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
  {
    id: 'spark',
    name: 'Apache Spark',
    layer: 'compute',
    stage: 'transformation',
    short: 'Streaming + batch jobs die Delta-tabellen op MinIO schrijven.',
    purpose: 'Zware data-bewerkingen — opschonen, joinen, aggregeren — in stream of batch.',
    icon: '/icons/brand/spark.svg',
    // Wijst naar de live driver-UI van de `streaming-bronze` SparkApplication
    // (via een eigen Service+Ingress, zie platform/08-spark/ingress.yaml).
    // Op de Executors-tab vind je stderr/stdout per pod = "spark cluster logs".
    // 503 als de driver niet draait.
    url: 'https://spark.odap.local:8443',
    embed: { mode: 'subdomain' },
    prometheusJob: 'spark',
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
  {
    id: 'trino',
    name: 'Trino',
    layer: 'query',
    stage: 'transformation',
    short: 'SQL query-engine over Delta-lakehouse, met OPA-authorisatie.',
    purpose: 'Snel SQL draaien over de hele lakehouse — voor dbt-modellen én eindgebruikers.',
    icon: '/icons/brand/trino.svg',
    // Trino-UI is bereikbaar onder de portal Compute-tab (embed iframe,
    // zelfde patroon als Spark). Eindgebruikers blijven Trino vooral via
    // Superset, Jupyter, dbt en Airflow gebruiken; de UI is handig voor
    // query-history, EXPLAIN-plans en het killen van runaway queries.
    url: 'https://trino.odap.local:8443',
    embed: { mode: 'subdomain' },
    prometheusJob: 'trino',
    rolesUsing: [
      'wia_beoordelaar',
      'ww_handhaver',
      'wajong_arbeidsdeskundige',
      'fez_analist',
      'smz_planner',
      'proactief_dienstverlener',
      'researcher',
      'data_steward',
      'data_engineer',
      'platform_admin',
    ],
  },
  {
    id: 'opa',
    name: 'OPA',
    layer: 'policy',
    stage: 'transformation',
    short: 'Open Policy Agent — beslist per Trino-query wat een rol mag zien (rij-filters, kolom-maskers, doelbinding).',
    purpose: 'Doelbinding, rij-filters en kolom-maskering afdwingen op iedere query.',
    icon: '/icons/brand/opa.svg',
    url: null,
    embed: { mode: 'none' },
    prometheusJob: 'opa',
    rolesUsing: ['platform_admin'],
  },
  {
    id: 'superset',
    name: 'Apache Superset',
    layer: 'bi',
    stage: 'consumption',
    short: 'Dashboards en SQL Lab — primaire UI voor de meeste eindgebruikers.',
    purpose: 'Dashboards en ad-hoc analyse voor business-rollen — zonder SQL hoeven kennen.',
    icon: '/icons/brand/superset.svg',
    url: 'https://superset.odap.local:8443',
    // Subdomain-routing — Superset hard-codet /superset als blueprint-
    // prefix voor z'n eigen klasse (Superset.welcome → /superset/welcome/),
    // dus nginx-rewrite + SCRIPT_NAME=/superset zou /superset/superset/...
    // produceren of bestaande routes als /welcome/ missen. Praktischer: blijft
    // op subdomein + ingress strip't X-Frame-Options + zet frame-ancestors.
    embed: { mode: 'subdomain' },
    prometheusJob: 'superset',
    rolesUsing: [
      'wia_beoordelaar',
      'ww_handhaver',
      'wajong_arbeidsdeskundige',
      'crm_medewerker',
      'fez_analist',
      'smz_planner',
      'proactief_dienstverlener',
      'researcher',
      'data_steward',
      'platform_admin',
    ],
  },
  {
    id: 'openmetadata',
    name: 'OpenMetadata',
    layer: 'governance',
    stage: 'discovery',
    short: 'Catalog, glossary, lineage, data-quality.',
    purpose: 'Wat hebben we, wie is eigenaar, hoe is het opgebouwd, en is het op orde?',
    icon: '/icons/brand/openmetadata.svg',
    url: 'https://openmetadata.odap.local:8443',
    // OpenMetadata 1.x heeft geen configureerbare context-path (alle /api/v1,
    // /callback, /entities zijn hard-coded). Blijft daarom cross-origin op
    // eigen subdomein; ingress strip't X-Frame-Options.
    embed: { mode: 'subdomain' },
    prometheusJob: 'openmetadata',
    rolesUsing: [
      'wia_beoordelaar',
      'ww_handhaver',
      'wajong_arbeidsdeskundige',
      'crm_medewerker',
      'fez_analist',
      'smz_planner',
      'researcher',
      'data_steward',
      'data_engineer',
      'platform_admin',
    ],
  },
  {
    id: 'dbt-docs',
    name: 'dbt docs',
    layer: 'governance',
    stage: 'discovery',
    // Statisch geëxporteerde `dbt docs generate --static`-bundel. Geserveerd
    // door de portal-nginx zelf op /dbt-docs/ — geen aparte service, geen
    // Prometheus-job (vandaar geen status-dot).
    short: 'Modellen, tests, sources en lineage van de dbt-projectdefinities.',
    purpose: 'Wat doen onze dbt-modellen, welke tests draaien er, en hoe vloeit data van staging naar marts?',
    icon: '/icons/brand/dbt.svg',
    url: '/dbt-docs.html',
    // dbt-docs is een statische bundle die door portal-nginx zelf wordt
    // geserveerd — same-origin per definitie.
    embed: { mode: 'subpath', path: '/dbt-docs.html' },
    rolesUsing: ['data_engineer', 'data_steward', 'platform_admin'],
  },
  {
    id: 'jupyter',
    name: 'ODAP Lab (Jupyter)',
    layer: 'compute',
    stage: 'consumption',
    short: 'Notebook-werkomgeving — Python/SQL op bronze/silver/gold/sensitive, met Git-integratie.',
    purpose: 'Interactief data verkennen en analyseren — Trino, Delta, MinIO, OpenMetadata vanuit één Python-kernel; werk versioneren met Git.',
    icon: '/icons/brand/jupyter.svg',
    url: 'https://jupyter.odap.local:8443',
    // JupyterHub draait onder c.JupyterHub.base_url = '/jupyter/'.
    // Notebook-kernels gebruiken websockets; nginx-ingress proxy_pass laat
    // die door zolang de Upgrade-header niet wordt geblokkeerd.
    embed: { mode: 'subpath', path: '/jupyter' },
    rolesUsing: [
      'researcher',
      'data_engineer',
      'data_steward',
      'wajong_arbeidsdeskundige',
      'fez_analist',
      'platform_admin',
    ],
  },
  {
    id: 'airflow',
    name: 'Apache Airflow',
    layer: 'orchestration',
    stage: 'pipeline',
    short: 'DAG-orchestratie voor batch-jobs en dbt-runs.',
    purpose: 'Plant en bewaakt alle scheduled jobs — wat draait wanneer, in welke volgorde.',
    icon: '/icons/brand/airflow.svg',
    url: 'https://airflow.odap.local:8443',
    // Airflow 3 — AIRFLOW__API__BASE_URL en AIRFLOW__FAB__BASE_URL beide
    // gezet op platform-host + /airflow. FAB proxy-fix met X_PREFIX zorgt
    // dat redirect_uri's correct worden opgebouwd onder subpath.
    embed: { mode: 'subpath', path: '/airflow' },
    prometheusJob: 'airflow',
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
  {
    id: 'prometheus',
    name: 'Prometheus',
    layer: 'observability',
    stage: 'observability',
    short: 'Metrics + alerts; voedt de status-badges in deze portal.',
    purpose: 'Metrics verzamelen en alerteren als iets stuk dreigt te gaan.',
    icon: '/icons/brand/prometheus.svg',
    url: 'https://prometheus.odap.local:8443',
    // --web.external-url=/prometheus + --web.route-prefix=/prometheus in
    // de Prometheus CR; geen auth dus geen cookie-overwegingen.
    embed: { mode: 'subpath', path: '/prometheus' },
    prometheusJob: 'prometheus-kube-prometheus-prometheus',
    rolesUsing: ['platform_admin'],
  },
  {
    id: 'grafana',
    name: 'Grafana',
    layer: 'observability',
    stage: 'observability',
    short: 'Dashboards over Prometheus-metrics — cluster-health en service-latency.',
    purpose: 'Visualisatie van Prometheus-metrics in dashboards; gateway voor SRE-werk.',
    icon: '/icons/brand/grafana.svg',
    // Login via Keycloak SSO (auth.generic_oauth in helm/prometheus-stack/values.yaml).
    // Klik op "Sign in with Keycloak" op de Grafana-loginpagina; admin-account
    // blijft beschikbaar als break-glass.
    url: 'https://grafana.odap.local:8443',
    // server.root_url + serve_from_sub_path=true in grafana.ini; werkt
    // schoon onder subpath.
    embed: { mode: 'subpath', path: '/grafana' },
    prometheusJob: 'prometheus-grafana',
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
  {
    id: 'opensearch',
    name: 'OpenSearch',
    layer: 'observability',
    stage: 'observability',
    short: 'Logs (Vector) + search-backend voor OpenMetadata.',
    purpose: 'Logs centraal doorzoekbaar maken — debugging en audit-trail.',
    icon: '/icons/brand/opensearch.svg',
    // Externe URL wijst naar OpenSearch Dashboards (port 5601). De REST-API
    // (port 9200) is alleen intern bereikbaar via cluster-DNS.
    url: 'https://opensearch.odap.local:8443',
    // OpenSearch Dashboards heeft een eigen oauth-flow; we houden 'm
    // cross-origin tot we tijd hebben voor server.basePath-config.
    embed: { mode: 'subdomain' },
    prometheusJob: 'opensearch',
    rolesUsing: ['platform_admin', 'data_steward'],
  },
  {
    id: 'multica',
    name: 'Multica',
    layer: 'ai-agents',
    stage: 'agents',
    // Dev-loop-lane: coördineert coding agents (Claude Code/Codex/Copilot CLI/…)
    // die op de laptop van de developer draaien — de server houdt taken,
    // voortgang en skills bij. Niet hetzelfde als Nanitics (runtime).
    short: 'Coördinatie van coding agents (Claude Code, Codex, Copilot CLI, …) — taken, voortgang, skills.',
    purpose: 'Taken toewijzen aan coding agents; voortgang volgen. Agents draaien op je laptop.',
    icon: '/icons/brand/multica.svg',
    url: 'https://multica.odap.local:8443',
    // Cross-origin op eigen subdomein achter oauth2-proxy; behoeft alleen
    // dat ingress X-Frame-Options niet zet.
    embed: { mode: 'subdomain' },
    prometheusJob: 'multica-backend',
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
  {
    id: 'powerbi',
    name: 'Power BI',
    layer: 'bi',
    stage: 'consumption',
    // Microsoft Power BI / Fabric als dashboarding-laag. Eindgebruikers
    // loggen in met hun eigen Azure-tenant (Entra ID SSO) op
    // app.fabric.microsoft.com — geen aparte account in dit cluster.
    //
    // Iframe-embedding: Microsoft stuurt voor app.fabric.microsoft.com een
    // restrictieve `Content-Security-Policy: frame-ancestors`-header, dus
    // de iframe wordt geblokt. EmbedLayout heeft een 8s-timeout die
    // automatisch de "Open in nieuw tabblad"-fallback toont — de gebruiker
    // landt dan direct op de Fabric-portal met SSO via z'n eigen tenant.
    //
    // Voor een echt-ingesloten ervaring (Power BI Embedded SDK +
    // App-Owns-Data + GenerateToken-backend) zie
    // FreshLakehouse/docs/research/powerbi-as-bi-and-self-service-layer.md
    // (Fase 4). Tot dat geïmplementeerd is, blijft 'subdomain' + fallback
    // de pragmatische default — sluit aan op bestaande embed-patronen.
    short: 'Dashboards en self-service exploration via Microsoft Fabric / Power BI (eigen Azure-tenant SSO).',
    purpose: 'Curated dashboards bovenop het lakehouse + composite-model self-service voor analisten met DAX/Excel-skills.',
    icon: '/icons/brand/powerbi.svg',
    url: 'https://app.fabric.microsoft.com',
    embed: { mode: 'subdomain', iframeBase: 'https://app.fabric.microsoft.com' },
    rolesUsing: [
      'wia_beoordelaar',
      'ww_handhaver',
      'wajong_arbeidsdeskundige',
      'crm_medewerker',
      'fez_analist',
      'smz_planner',
      'proactief_dienstverlener',
      'researcher',
      'data_analyst',
      'data_steward',
      'platform_admin',
    ],
  },
  {
    id: 'nanitics',
    name: 'Nanitics Observatory',
    layer: 'ai-agents',
    stage: 'agents',
    // Runtime-lane: in-cluster FastAPI + Nanitics SDK met vier demo-agents
    // (ReAct/ReWOO/Reflexion/LATS) plús een platform-watcher die periodiek
    // Prometheus/K8s-events/OpenSearch leest en bevindingen als Multica-tasks
    // filed in `platform-ops`. URL wijst naar de Observatory trace-viewer;
    // /chat is een tweede entry voor handmatige watcher-triggers.
    short: 'In-cluster agent-runtime + trace-viewer. Watcher monitort het platform en filed issues naar Multica.',
    purpose: 'Bekijk watcher-runs (span tree, LLM-calls, tool-calls) en triggert handmatige investigations.',
    // Geen eigen brand-svg; valt terug op het generieke agents-stage-icoon
    // tot er een Nanitics-logo aan public/icons/brand/ is toegevoegd.
    icon: '/icons/stage/agents.svg',
    url: 'https://nanitics.odap.local:8443/api/observatory/',
    embed: { mode: 'subdomain' },
    rolesUsing: ['platform_admin', 'data_engineer'],
  },
];

export function componentsForRole(role: string): PlatformComponent[] {
  return components.filter(
    (c) => c.rolesUsing.includes('*') || c.rolesUsing.includes(role),
  );
}

export function componentById(id: ComponentId): PlatformComponent | undefined {
  return components.find((c) => c.id === id);
}

export function componentsByStage(stage: ComponentStage): PlatformComponent[] {
  return components.filter((c) => c.stage === stage);
}

/**
 * Of een component in de portal-iframe-shell past. False voor Keycloak,
 * Kafka, Hive, OPA, Trino — die hebben geen iframe-bare UI.
 */
export function isEmbeddable(c: PlatformComponent): boolean {
  return c.embed != null && c.embed.mode !== 'none';
}

/**
 * Componenten die /embed/<id>-pagina krijgen. Gebruikt door
 * getStaticPaths() in pages/embed/[id].astro.
 */
export function embeddableComponents(): PlatformComponent[] {
  return components.filter(isEmbeddable);
}

/**
 * Href die in de portal-UI (architectuur-diagram, role-shortcuts, /me)
 * gebruikt moet worden bij een klik op een component. Voor iframe-bare
 * componenten landt 'ie in /embed/<id>/ (portal-shell); anders de
 * originele externe URL (Keycloak, MinIO-via-go-redirect, etc.).
 */
export function tileHref(c: PlatformComponent): string | null {
  if (isEmbeddable(c)) return `/embed/${c.id}/`;
  return c.url;
}

/**
 * Resolveert de iframe-src URL voor een component, optioneel met deep-link
 * pad. Bouwt op build-time de odap.local-URL; Layout.astro's
 * runtime TLD-rewrite swap't naar de juiste cloud-host. De DEEP-LINK is een
 * pad-inclusief-query (bv. "/dashboard/list/?filters=…") relatief aan de
 * service-root.
 */
export function resolveEmbedSrc(
  c: PlatformComponent,
  deepLink?: string | null,
): string | null {
  if (!c.embed) return null;

  // 'none' → niet iframe-baar; caller toont een "open in nieuw tabblad"-fallback.
  if (c.embed.mode === 'none') return null;

  const cleanDeep = (deepLink ?? '').trim();
  // Voor 'subpath' bouwen we platform-host + path + deep-link.
  // De runtime rewrite in Layout.astro raakt 'm niet aan want geen
  // *.odap.local hostname.
  // Path die op een bestand wijst (bv. `/dbt-docs.html`) krijgt geen
  // trailing slash — anders bouwen we `/dbt-docs.html/` en dat 404't.
  // Heuristic: een laatste segment met een '.' is een bestand.
  const looksLikeFile = (p: string) => /\.[a-z0-9]+$/i.test(p.split('/').pop() ?? '');

  if (c.embed.mode === 'subpath') {
    const raw = c.embed.path ?? '/';
    const base = raw.replace(/\/+$/, '');
    if (!cleanDeep) return looksLikeFile(base) ? base : base + '/';
    // Deep-link mag met of zonder '/' beginnen — normaliseer.
    return base + (cleanDeep.startsWith('/') ? cleanDeep : '/' + cleanDeep);
  }

  // 'subdomain' → externe URL uit embed.iframeBase (override) of c.url.
  if (c.embed.mode === 'subdomain') {
    const source = c.embed.iframeBase ?? c.url;
    if (!source) return null;
    const baseUrl = source.replace(/\/+$/, '');
    if (!cleanDeep) return looksLikeFile(baseUrl) ? baseUrl : baseUrl + '/';
    return baseUrl + (cleanDeep.startsWith('/') ? cleanDeep : '/' + cleanDeep);
  }

  return null;
}

/**
 * Bouwt de externe (open-in-new-tab) URL voor een component, inclusief
 * eventueel deep-link pad. Voor subpath-componenten plakken we op de
 * portal-host, voor subdomain-componenten op de service-host.
 *
 * Wordt door EmbedShell gebruikt voor de "↗ open in nieuw tabblad"-knop.
 */
export function resolveExternalUrl(
  c: PlatformComponent,
  deepLink?: string | null,
): string | null {
  const cleanDeep = (deepLink ?? '').trim();
  const looksLikeFile = (p: string) => /\.[a-z0-9]+$/i.test(p.split('/').pop() ?? '');

  if (c.embed?.mode === 'subpath') {
    const base = (c.embed.path ?? '/').replace(/\/+$/, '');
    if (!cleanDeep) return looksLikeFile(base) ? base : base + '/';
    return base + (cleanDeep.startsWith('/') ? cleanDeep : '/' + cleanDeep);
  }
  // Subdomain mode: voor "open in nieuw tabblad" gebruiken we dezelfde
  // base als de iframe — gebruiker landt op de echte service-URL, niet op
  // een tussenpagina als /go/minio/.
  if (c.embed?.mode === 'subdomain' && c.embed.iframeBase) {
    const baseUrl = c.embed.iframeBase.replace(/\/+$/, '');
    if (!cleanDeep) return baseUrl;
    return baseUrl + (cleanDeep.startsWith('/') ? cleanDeep : '/' + cleanDeep);
  }
  if (!c.url) return null;
  if (c.url.startsWith('/')) return c.url; // portal-interne URL (zoals dbt-docs)
  const baseUrl = c.url.replace(/\/+$/, '');
  if (!cleanDeep) return baseUrl;
  return baseUrl + (cleanDeep.startsWith('/') ? cleanDeep : '/' + cleanDeep);
}

// Stage-meta voor lane-headers in het reference-diagram en gegroepeerde
// kaarten. Volgorde hier bepaalt de volgorde van de swim-lanes.
export type StageCategory = 'discovery' | 'pipeline' | 'observability' | 'identity' | 'agents';

export interface StageMeta {
  id: ComponentStage;
  title: string;
  blurb: string;
  icon: string;
  // Legacy field used by the older diagram. 'pipeline-step' = main flow;
  // 'overlay' = cross-cutting (discovery / pipeline / observability /
  // agents); 'side' = sources / identity; 'output' = consumption.
  kind: 'pipeline-step' | 'overlay' | 'side' | 'output';
  // For the swim-lane diagram: tints the lane background and eyebrow with
  // the matching --cat-* token. Pipeline-step / output / sources lanes
  // stay neutral.
  category?: StageCategory;
  // Mono tags shown next to the lane title (BATCH / STREAM / etc.).
  tags?: string[];
}

export const stages: StageMeta[] = [
  { id: 'sources',        title: 'Bronnen',                  blurb: 'Synthetische UWV-bronsystemen — batches en streams.',                  icon: '/icons/stage/sources.svg',        kind: 'side',          tags: ['BATCH', 'STREAM'] },
  { id: 'ingestion',      title: 'Ingestie',                 blurb: 'Data binnenhalen en op een event-bus zetten.',                          icon: '/icons/stage/ingestion.svg',      kind: 'pipeline-step', tags: ['BATCH', 'STREAM'] },
  { id: 'storage',        title: 'Opslag & Verwerking',      blurb: 'Lakehouse met zones en een tabel-catalog.',                              icon: '/icons/stage/storage.svg',        kind: 'pipeline-step', tags: ['LAKEHOUSE'] },
  { id: 'transformation', title: 'Transformatie & Modellen', blurb: 'Opschonen, joinen, modelleren — met policy-checks per query.',          icon: '/icons/stage/transformation.svg', kind: 'pipeline-step', tags: ['BATCH', 'POLICY'] },
  { id: 'consumption',    title: 'BI / Analytics',           blurb: 'Eindgebruikers consumeren via dashboards en SQL.',                       icon: '/icons/stage/consumption.svg',    kind: 'output',        tags: ['QUERY'] },
  { id: 'discovery',      title: 'Data Discovery',           blurb: 'Catalog, lineage en data-kwaliteit — wat hebben we eigenlijk?',         icon: '/icons/stage/discovery.svg',      kind: 'overlay',       category: 'discovery' },
  { id: 'pipeline',       title: 'Pipeline-orkestratie',     blurb: 'Wat draait wanneer, in welke volgorde, met welke afhankelijkheid.',     icon: '/icons/stage/pipeline.svg',       kind: 'overlay',       category: 'pipeline' },
  { id: 'observability',  title: 'Observability',            blurb: 'Metrics, logs en alerts om de gezondheid van het platform te zien.',    icon: '/icons/stage/observability.svg',  kind: 'overlay',       category: 'observability' },
  { id: 'identity',       title: 'Identiteit & Toegang',     blurb: 'SSO regelt wie wat mag — elk onderdeel checkt het token.',              icon: '/icons/stage/identity.svg',       kind: 'side',          category: 'identity' },
  // Agents-lane: Multica coördineert coding-agents (dev-loop, op de laptop
  // van de developer), Nanitics Observatory is de in-cluster runtime + trace-
  // viewer voor platform-watcher-agents. Beide zijn onderdeel van het platform.
  { id: 'agents',         title: 'Agents & AI-tooling',      blurb: 'Coördinatie van coding agents (Multica) plus de in-cluster agent-runtime (Nanitics Observatory).', icon: '/icons/stage/agents.svg',         kind: 'overlay',       category: 'agents' },
];

export function stageById(id: ComponentStage): StageMeta | undefined {
  return stages.find((s) => s.id === id);
}
