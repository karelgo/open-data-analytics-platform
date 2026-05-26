// Curated shortcuts per rol — handmatig onderhouden, geen afgeleide data.
// Past bij de "dagelijkse workflows" uit docs/handleidingen/<rol>.md.
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
  wia_beoordelaar: [
    { title: 'WIA Funnel dashboard', hint: 'Voorraad en doorlooptijden in jouw regio', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:wia-funnel)' },
    { title: 'SQL Lab — open > 8 weken', hint: 'Wettelijke termijn-overschrijdingen', component: 'superset', href: 'https://superset.odap.local:8443/sqllab/' },
    { title: 'Tabel: silver.wia.aanvraag', hint: 'Definities en eigenaren opzoeken', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/table/trino.silver.wia.aanvraag' },
  ],
  ww_handhaver: [
    { title: 'WW Risk dashboard', hint: 'Risico-scores per dossier', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:ww-risk)' },
    { title: 'Lineage WW-funnel', hint: 'Bron → silver → gold', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/lineage/trino.gold.uc03_ww_risk' },
  ],
  wajong_arbeidsdeskundige: [
    { title: 'UC02 Wajong dashboard', hint: 'Reïntegratie-trajecten', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:uc02-wajong)' },
    { title: 'Glossary: „participatie” termen', hint: 'Begrippen opéén plek', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/glossary' },
  ],
  crm_medewerker: [
    { title: 'Klant 360 (UC-05)', hint: 'BSN gemaskeerd, alleen klantcontact-doel', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:client-360)' },
    { title: 'Tabel: gold.uc05_client_360', hint: 'Welke kolommen je ziet', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/table/trino.gold.uc05_client_360' },
  ],
  fez_analist: [
    { title: 'Lastprognose (UC-06)', hint: 'Geaggregeerde uitkeringen, geen PII', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:uc06-lastprognose)' },
    { title: 'Tabel: gold.uc06_lastprognose', hint: 'Definities + eigenaar', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/table/trino.gold.uc06_lastprognose' },
    { title: 'ODAP Lab — ad-hoc analyse', hint: 'Notebook met polars/pandas op gold-aggregaten', component: 'jupyter', href: 'https://jupyter.odap.local:8443' },
  ],
  smz_planner: [
    { title: 'SMZ Capaciteitsplanning', hint: 'UC-08 — geen cliënt-PII', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:uc08-smz)' },
    { title: 'Glossary: spreekuur-typen', hint: 'Welke planning-categorieën bestaan', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/glossary' },
  ],
  proactief_dienstverlener: [
    { title: 'TW-eligibility werklijst', hint: 'UC-04 — opt-out gefilterd', component: 'superset', href: 'https://superset.odap.local:8443/dashboard/list/?filters=(slug:uc04-tw)' },
    { title: 'Doelbinding & opt-out', hint: 'Welke regels gelden voor proactief contact', component: 'openmetadata', href: 'https://openmetadata.odap.local:8443/glossary/term/proactieve_dienstverlening' },
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
