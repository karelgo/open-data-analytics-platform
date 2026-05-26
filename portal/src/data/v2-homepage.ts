/*
  v2-homepage.ts — data for the v2 workspace homepage.

  Used by:
    - src/pages/index.astro                   (live /)
    - src/pages/styleguide/portal-v2.astro    (mockup showcase)
    - src/components/shell/WorkspaceHome.astro

  RECENTS + HERO_STATS start empty and are filled client-side from
  /api/portal/recents resp. /api/portal/stats (the stats endpoint
  is still TODO — see fase 2). EXPLORE is static and mirrors
  src/data/components.ts categories.
*/

// Item type drives the colour-tint behind the brand icon and the chip label.
export type ItemType =
  | 'dashboard' | 'dag' | 'table' | 'notebook' | 'query' | 'pipeline';

// Service slug — must match a filename in portal/public/icons/brand/.
export type ServiceSlug =
  | 'airflow' | 'dbt' | 'grafana' | 'hive' | 'jupyter' | 'kafka'
  | 'keycloak' | 'minio' | 'multica' | 'nifi' | 'opa' | 'openmetadata'
  | 'opensearch' | 'powerbi' | 'prometheus' | 'spark' | 'superset' | 'trino';

export interface RecentItem {
  type: ItemType;
  service: ServiceSlug;
  title: string;
  subtitle: string;
  owner: string;
  status: 'ok' | 'warn' | 'down' | null;
  starred: boolean;
  href: string;
}

export interface ExploreItem {
  type: ItemType;
  service: ServiceSlug;
  title: string;
  subtitle: string;
  href: string;
}

export interface ExploreCategory {
  title: string;
  sub: string;
  items: ExploreItem[];
}

// Recent items — most-recently-opened by the user.
// Empty by default. WorkspaceHome's client-side script fetches
// /api/portal/recents and renders the live history; if the backend
// is unreachable the section stays empty (better than misleading
// hardcoded sample data in production).
export const RECENTS: RecentItem[] = [];

// "Explore" — all platform services, grouped by stage.
// Each tile lands on the embed route for that service; for services
// without an iframe-safe UI (Trino, NiFi, Kafka, Hive, OPA), the
// EmbedLayout shows a fallback card with "open in new tab".
export const EXPLORE: ExploreCategory[] = [
  {
    title: 'Pipeline & Compute',
    sub:   'Ingest, transform, query',
    items: [
      { type: 'dag',      service: 'airflow', title: 'Airflow', subtitle: 'Orchestration',       href: '/embed/airflow/' },
      { type: 'pipeline', service: 'spark',   title: 'Spark',   subtitle: 'Distributed compute', href: '/embed/spark/' },
      { type: 'query',    service: 'trino',   title: 'Trino',   subtitle: 'SQL engine',          href: '/embed/trino/' },
      { type: 'pipeline', service: 'dbt',     title: 'dbt',     subtitle: 'Transformations',     href: '/embed/dbt-docs/' },
      { type: 'dag',      service: 'nifi',    title: 'NiFi',    subtitle: 'Stream ingestion',    href: '/embed/nifi/' },
      { type: 'pipeline', service: 'kafka',   title: 'Kafka',   subtitle: 'Event streaming',     href: '/embed/kafka/' },
    ],
  },
  {
    title: 'BI & Analytics',
    sub:   'Dashboards, queries, notebooks',
    items: [
      { type: 'dashboard', service: 'superset', title: 'Superset', subtitle: 'Dashboards + SQLLab',          href: '/embed/superset/' },
      { type: 'dashboard', service: 'powerbi',  title: 'Power BI', subtitle: 'Fabric SDK-embed (Entra SSO)', href: '/embed/powerbi/' },
      { type: 'notebook',  service: 'jupyter',  title: 'Jupyter',  subtitle: 'Notebooks (Trino+Delta)',      href: '/embed/jupyter/' },
      { type: 'pipeline',  service: 'dbt',      title: 'dbt-docs', subtitle: 'Lineage + tests',              href: '/embed/dbt-docs/' },
    ],
  },
  {
    title: 'Catalog & Governance',
    sub:   'Discover, lineage, policies',
    items: [
      { type: 'table', service: 'openmetadata', title: 'OpenMetadata', subtitle: 'Catalog + lineage', href: '/embed/openmetadata/' },
      { type: 'table', service: 'minio',        title: 'MinIO',        subtitle: 'Object storage',    href: '/embed/minio/' },
      { type: 'table', service: 'hive',         title: 'Hive',         subtitle: 'Metastore',         href: '/embed/hive/' },
      { type: 'query', service: 'opa',          title: 'OPA',          subtitle: 'Policy engine',     href: '/embed/opa/' },
    ],
  },
  {
    title: 'Observability',
    sub:   'Metrics, logs, traces',
    items: [
      { type: 'dashboard', service: 'grafana',    title: 'Grafana',    subtitle: 'Metrics dashboards', href: '/embed/grafana/' },
      { type: 'query',     service: 'opensearch', title: 'OpenSearch', subtitle: 'Vector log search',  href: '/embed/opensearch/' },
      { type: 'pipeline',  service: 'prometheus', title: 'Prometheus', subtitle: 'Metrics scrape',     href: '/embed/prometheus/' },
    ],
  },
];

// Hero stats — TODO fase 2: fetch from /api/portal/stats.
// Empty by default; no SSR fallback because hardcoded counts mislead
// users about real platform state.
export interface HeroStat {
  value: string;
  label: string;
  tone?: 'down' | 'ok' | 'warn';
}
export const HERO_STATS: HeroStat[] = [];
