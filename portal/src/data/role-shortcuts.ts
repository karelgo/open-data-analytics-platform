// Curated shortcuts per rol — handmatig onderhouden, geen afgeleide data.
// Past bij de "dagelijkse workflows" uit docs/handbooks/<rol>.md.
//
// Toevoegen van een shortcut = één entry hier; verschijnt automatisch op /me.

import type { RoleId } from './roles';
import { components, type ComponentId, isEmbeddable } from './components';

export interface Shortcut {
  title: string;
  hint: string;
  component: ComponentId;
  href: string;
}

/**
 * Converteer een rauwe service-URL uit een Shortcut naar een
 * /embed/<id>?path=<deep-link>-pad, zodat de klik in de portal-shell
 * landt in plaats van een tab-switch naar het oude subdomein.
 *
 * - Voor componenten die niet iframe-baar zijn (`embed.mode === 'none'`):
 *   we laten de originele href ongewijzigd; /me linkt gewoon naar buiten.
 * - Voor portal-interne URLs (`/dbt-docs.html`, `/go/minio/`): href blijft
 *   ongewijzigd. /go/minio/ heeft een SSO-bootstrap die we niet willen
 *   omzeilen door direct in een iframe naar de Console te springen.
 * - Voor externe URLs van iframe-bare componenten: pak het pad-deel uit
 *   de URL en bouw `/embed/<id>?path=<pad-met-query>`.
 */
export function toEmbedHref(s: Shortcut): string {
  const comp = components.find((c) => c.id === s.component);
  if (!comp || !isEmbeddable(comp)) return s.href;
  // Portal-interne URL (start met '/' maar geen '//'): laat staan.
  if (s.href.startsWith('/') && !s.href.startsWith('//')) return s.href;
  if (!/^https?:\/\//i.test(s.href)) return s.href;
  try {
    const u = new URL(s.href);
    const deep = u.pathname + u.search + u.hash;
    // Geen pad / root: stuur naar /embed/<id>.
    if (deep === '/' || deep === '') return `/embed/${comp.id}/`;
    return `/embed/${comp.id}/?path=${encodeURIComponent(deep)}`;
  } catch {
    return s.href;
  }
}

export const shortcuts: Record<RoleId, Shortcut[]> = {
  claims_analyst: [
    { title: 'Claims Funnel dashboard', hint: 'Backlog and lead-time in your region', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:claims-funnel)' },
    { title: 'SQL Lab — claims open > 8 weeks', hint: 'Statutory deadline overruns', component: 'superset', href: 'https://superset.odap.local:8443/sqllab/' },
    { title: 'Table: silver.claims.application', hint: 'Look up definitions and owners', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/table/trino.silver.claims.application' },
    { title: 'Complex-case dashboard', hint: 'Sensitive zone — four-eyes required', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:uc02-complex-cases)' },
    { title: 'Glossary: case-handling terms', hint: 'Definitions in one place', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/glossary' },
  ],
  fraud_analyst: [
    { title: 'Fraud Risk dashboard', hint: 'Risk scores per case', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:fraud-risk)' },
    { title: 'Lineage fraud funnel', hint: 'Source → silver → gold', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/lineage/trino.gold.uc03_fraud_risk' },
  ],
  marketing_analyst: [
    { title: 'Customer 360 (UC-05)', hint: 'PII visible, customer-contact purpose only', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:customer-360)' },
    { title: 'Table: gold.uc05_customer_360', hint: 'Which columns you can see', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/table/trino.gold.uc05_customer_360' },
    { title: 'Eligibility outreach worklist', hint: 'UC-04 — opt-out filtered', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:uc04-outreach)' },
    { title: 'Purpose & opt-out', hint: 'Rules that apply to proactive outreach', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/glossary/term/proactive_outreach' },
  ],
  finance_analyst: [
    { title: 'Cost forecast (UC-06)', hint: 'Aggregated cost figures, no PII', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:uc06-forecast)' },
    { title: 'Table: gold.uc06_forecast', hint: 'Definitions + owner', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/table/trino.gold.uc06_forecast' },
    { title: 'ODAP Lab — ad-hoc analysis', hint: 'Notebook with polars/pandas on gold aggregates', component: 'jupyter', href: 'https://jupyter.odap.local:8443' },
  ],
  operations_manager: [
    { title: 'Capacity planning', hint: 'UC-08 — no customer PII', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:uc08-capacity)' },
    { title: 'Glossary: planning types', hint: 'Which planning categories exist', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/glossary' },
  ],
  researcher: [
    { title: 'ODAP Lab (notebooks)', hint: 'Jupyter + Trino + Delta — research op sandbox-data, versioneer met Git', component: 'jupyter', href: 'https://jupyter.odap.local:8443' },
    { title: 'Lineage UC-09', hint: 'Hoe het sandbox-panel is opgebouwd', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/lineage/trino.sandbox.uc09_research' },
  ],
  data_steward: [
    { title: 'DQ-overzicht (alle UCs)', hint: 'Cross-UC violations + DQ-score per use-case', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:dq-overview)' },
    { title: 'DQ-violations detail', hint: 'Drill-down per check × severity', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:dq-violations-detail)' },
    { title: 'Data Quality dashboard', hint: 'DQ-checks en profielen', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/data-quality' },
    { title: 'Glossary onderhouden', hint: 'Termen, eigenaars, classificaties', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/glossary' },
    { title: 'dbt docs — modellen & tests', hint: 'Statische export van dbt-projectdefinities', component: 'dbt-docs', href: '/dbt-docs.html' },
    { title: 'Notebook DQ-checks (ODAP Lab)', hint: 'Scripted DQ via OpenMetadata-API in Jupyter', component: 'jupyter', href: 'https://jupyter.odap.local:8443' },
  ],
  data_engineer: [
    { title: 'Airflow DAGs', hint: 'Batch- en dbt-runs', component: 'airflow', href: 'https://airflow.odap.local:8443' },
    { title: 'dbt docs — modellen & lineage', hint: 'Welk model leest welke source, welke tests draaien', component: 'dbt-docs', href: '/dbt-docs.html' },
    { title: 'ODAP Lab (notebooks)', hint: 'Ad-hoc PySQL / Delta-rs op de lakehouse — git-backed', component: 'jupyter', href: 'https://jupyter.odap.local:8443' },
    { title: 'MinIO buckets', hint: 'bronze/silver/gold/sensitive', component: 'minio', href: '/go/minio/' },
    { title: 'Grafana dashboards', hint: 'Pipeline-latency, Spark/Trino metrics — login via Keycloak', component: 'grafana', href: '/embed/grafana/' },
    { title: 'JIT-toegang aanvragen', hint: 'Bronze alleen met just-in-time', component: 'keycloak', href: 'https://keycloak.odap.local:8443/realms/odap/account' },
  ],
  platform_admin: [
    { title: 'Cluster-status (Prometheus)', hint: 'Up/Down per service', component: 'prometheus', href: 'https://prometheus.odap.local:8443' },
    { title: 'Grafana dashboards', hint: 'Cluster-health en service-latency — login via Keycloak SSO', component: 'grafana', href: '/embed/grafana/' },
    { title: 'Keycloak admin', hint: 'Users, rollen, MFA', component: 'keycloak', href: 'https://keycloak.odap.local:8443/admin' },
    { title: 'OpenSearch Dashboards', hint: 'Discover op logs-* — audit + applicatie-logs', component: 'opensearch', href: 'https://opensearch.odap.local:8443/app/data-explorer/discover' },
    { title: 'Break-glass procedure', hint: 'Alleen in nood; alles wordt gelogd', component: 'opa', href: 'docs/runbook.md' },
  ],
};
