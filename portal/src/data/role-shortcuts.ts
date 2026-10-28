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
 * landt in plaats van een tab-switch to the oude subdomein.
 *
 * - Voor components die niet iframe-baar zijn (`embed.mode === 'none'`):
 *   we laten de originele href ongewijzigd; /me linkt gewoon naar buiten.
 * - Voor portal-interne URLs (`/dbt-docs.html`, `/go/minio/`): href blijft
 *   ongewijzigd. /go/minio/ heeft een SSO-bootstrap die we niet willen
 *   omzeilen door direct in een iframe to the Console te springen.
 * - Voor externe URLs van iframe-bare components: pak het pad-deel uit
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

const jobMarketShortcuts: Shortcut[] = [
  { title: 'Dutch IT jobs', hint: 'Demand, skills, pay and provenance across six domains', component: 'superset', href: '/job-market/' },
  { title: 'Job-market dashboard', hint: 'Database-backed Gold analytics', component: 'superset', href: '/embed/superset/?path=/superset/dashboard/dutch-it-job-market/' },
  { title: 'Job inventory in the catalog', hint: 'Definitions, owner, tests and lineage', component: 'openmetadata', href: '/embed/openmetadata/?path=/table/trino.gold.job_market.mart_job_inventory' },
  { title: 'Job-market notebook', hint: 'SQLite locally, Trino on the platform', component: 'jupyter', href: '/embed/jupyter/' },
];

export const shortcuts: Record<RoleId, Shortcut[]> = {
  claims_analyst: [...jobMarketShortcuts],
  fraud_analyst: [...jobMarketShortcuts],
  marketing_analyst: [...jobMarketShortcuts],
  finance_analyst: [...jobMarketShortcuts],
  operations_manager: [...jobMarketShortcuts],
  researcher: [...jobMarketShortcuts],
  data_steward: [...jobMarketShortcuts],
  data_engineer: [...jobMarketShortcuts],
  platform_admin: [...jobMarketShortcuts],
};
