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
    short: 'OIDC identity provider — single sign-on and MFA for every component.',
    purpose: 'One sign-in, role-based access everywhere. Central MFA and audit log.',
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
    short: 'Visual ingestion flows — source systems → Kafka.',
    purpose: 'Pull data from source systems into the platform.',
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
    short: 'Event bus between NiFi ingestion and Spark Structured Streaming.',
    purpose: 'Buffer data events and forward them to processing. Scalable throughput.',
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
    short: 'S3-compatible object store with buckets bronze/silver/gold/sensitive.',
    purpose: 'The lakehouse where all data physically lives — layered in zones with separate access rules.',
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
    short: 'Catalog backend — tracks table schemas and partitions for Trino and Spark.',
    purpose: 'Translates files in MinIO into tables with columns and types.',
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
    short: 'Streaming + batch jobs that write Delta tables on MinIO.',
    purpose: 'Heavy data work — cleaning, joining, aggregating — in stream or batch.',
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
    short: 'SQL query engine over the Delta lakehouse, with OPA authorization.',
    purpose: 'Run SQL fast over the entire lakehouse — for dbt models and end users alike.',
    icon: '/icons/brand/trino.svg',
    // Trino-UI is bereikbaar onder de portal Compute-tab (embed iframe,
    // zelfde patroon als Spark). Eindgebruikers blijven Trino vooral via
    // Superset, Jupyter, dbt en Airflow gebruiken; de UI is handig voor
    // query-history, EXPLAIN-plans en het killen van runaway queries.
    url: 'https://trino.odap.local:8443',
    embed: { mode: 'subdomain' },
    prometheusJob: 'trino',
    rolesUsing: [
      'claims_analyst',
      'fraud_analyst',
      'finance_analyst',
      'operations_manager',
      'marketing_analyst',
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
    short: 'Open Policy Agent — decides per Trino query what a role may see (row filters, column masks, purpose limitation).',
    purpose: 'Enforce purpose limitation, row filters, and column masking on every query.',
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
    short: 'Dashboards and SQL Lab — primary UI for most end users.',
    purpose: 'Dashboards and ad-hoc analysis for business roles — no SQL knowledge required.',
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
      'claims_analyst',
      'fraud_analyst',
      'marketing_analyst',
      'finance_analyst',
      'operations_manager',
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
    short: 'Catalog, glossary, lineage, data quality.',
    purpose: 'What do we have, who owns it, how is it built, and is it in good shape?',
    icon: '/icons/brand/openmetadata.svg',
    url: 'https://openmetadata.odap.local:8443',
    // OpenMetadata 1.x heeft geen configureerbare context-path (alle /api/v1,
    // /callback, /entities zijn hard-coded). Blijft daarom cross-origin op
    // eigen subdomein; ingress strip't X-Frame-Options.
    embed: { mode: 'subdomain' },
    prometheusJob: 'openmetadata',
    rolesUsing: [
      'claims_analyst',
      'fraud_analyst',
      'marketing_analyst',
      'finance_analyst',
      'operations_manager',
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
    short: 'Models, tests, sources, and lineage from the dbt project definitions.',
    purpose: 'What do our dbt models do, which tests run, and how does data flow from staging to marts?',
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
    short: 'Notebook environment — Python/SQL on bronze/silver/gold/sensitive, with Git integration.',
    purpose: 'Interactively explore and analyse data — Trino, Delta, MinIO, OpenMetadata from one Python kernel; version work with Git.',
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
      'claims_analyst',
      'finance_analyst',
      'platform_admin',
    ],
  },
  {
    id: 'airflow',
    name: 'Apache Airflow',
    layer: 'orchestration',
    stage: 'pipeline',
    short: 'DAG orchestration for batch jobs and dbt runs.',
    purpose: 'Schedules and monitors all scheduled jobs — what runs when, in what order.',
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
    short: 'Metrics + alerts; feeds the status badges in this portal.',
    purpose: 'Collect metrics and alert when something is about to break.',
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
    short: 'Dashboards on Prometheus metrics — cluster health and service latency.',
    purpose: 'Visualise Prometheus metrics in dashboards; gateway for SRE work.',
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
    short: 'Logs (Vector) + search backend for OpenMetadata.',
    purpose: 'Make logs centrally searchable — debugging and audit trail.',
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
    short: 'Coordination of coding agents (Claude Code, Codex, Copilot CLI, …) — tasks, progress, skills.',
    purpose: 'Assign tasks to coding agents; track progress. Agents run on your laptop.',
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
    short: 'Dashboards and self-service exploration via Microsoft Fabric / Power BI (own Azure-tenant SSO).',
    purpose: 'Curated dashboards on top of the lakehouse + composite-model self-service for analysts with DAX/Excel skills.',
    icon: '/icons/brand/powerbi.svg',
    url: 'https://app.fabric.microsoft.com',
    embed: { mode: 'subdomain', iframeBase: 'https://app.fabric.microsoft.com' },
    rolesUsing: [
      'claims_analyst',
      'fraud_analyst',
      'marketing_analyst',
      'finance_analyst',
      'operations_manager',
      'researcher',
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
    short: 'In-cluster agent runtime + trace viewer. Watcher monitors the platform and files issues to Multica.',
    purpose: 'Inspect watcher runs (span tree, LLM calls, tool calls) and trigger manual investigations.',
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
  { id: 'sources',        title: 'Sources',                  blurb: 'Synthetic source systems — batches and streams.',                       icon: '/icons/stage/sources.svg',        kind: 'side',          tags: ['BATCH', 'STREAM'] },
  { id: 'ingestion',      title: 'Ingestion',                blurb: 'Pull data from source systems onto an event bus.',                      icon: '/icons/stage/ingestion.svg',      kind: 'pipeline-step', tags: ['BATCH', 'STREAM'] },
  { id: 'storage',        title: 'Storage & Processing',     blurb: 'Lakehouse with zones and a table catalog.',                             icon: '/icons/stage/storage.svg',        kind: 'pipeline-step', tags: ['LAKEHOUSE'] },
  { id: 'transformation', title: 'Transformation & Models',  blurb: 'Clean, join, and model — with policy checks per query.',                icon: '/icons/stage/transformation.svg', kind: 'pipeline-step', tags: ['BATCH', 'POLICY'] },
  { id: 'consumption',    title: 'BI / Analytics',           blurb: 'End users consume through dashboards and SQL.',                         icon: '/icons/stage/consumption.svg',    kind: 'output',        tags: ['QUERY'] },
  { id: 'discovery',      title: 'Data Discovery',           blurb: 'Catalog, lineage, and data quality — what do we actually have?',        icon: '/icons/stage/discovery.svg',      kind: 'overlay',       category: 'discovery' },
  { id: 'pipeline',       title: 'Pipeline orchestration',   blurb: 'What runs when, in what order, with which dependencies.',               icon: '/icons/stage/pipeline.svg',       kind: 'overlay',       category: 'pipeline' },
  { id: 'observability',  title: 'Observability',            blurb: 'Metrics, logs, and alerts for monitoring platform health.',             icon: '/icons/stage/observability.svg',  kind: 'overlay',       category: 'observability' },
  { id: 'identity',       title: 'Identity & Access',        blurb: 'SSO governs who may do what — every component checks the token.',       icon: '/icons/stage/identity.svg',       kind: 'side',          category: 'identity' },
  // Agents lane: Multica coordinates coding agents (dev loop, on the developer's
  // laptop); Nanitics Observatory is the in-cluster runtime + trace viewer for
  // platform-watcher agents. Both are part of the platform.
  { id: 'agents',         title: 'Agents & AI tooling',      blurb: 'Coordination of coding agents (Multica) plus the in-cluster agent runtime (Nanitics Observatory).', icon: '/icons/stage/agents.svg',         kind: 'overlay',       category: 'agents' },
];

export function stageById(id: ComponentStage): StageMeta | undefined {
  return stages.find((s) => s.id === id);
}
