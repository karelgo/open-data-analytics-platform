// Track-metadata: koppelt rollen aan een korte trackomschrijving en aan de
// volgorde van de drie levels. Modules zelf staan als MDX in src/content/learn.

import type { RoleId } from './roles';

export type Level = 'foundation' | 'practitioner' | 'expert';

export interface LevelMeta {
  id: Level;
  title: string;
  blurb: string;
}

export const levels: LevelMeta[] = [
  { id: 'foundation',   title: 'Foundation',   blurb: 'Wat is dit platform en wat doet jouw rol erop?' },
  { id: 'practitioner', title: 'Practitioner', blurb: 'Hands-on: één concrete taak van begin tot eind.' },
  { id: 'expert',       title: 'Expert',       blurb: 'Eigen werk leveren — bouwen, reviewen, troubleshooten.' },
];

export interface TrackMeta {
  role: RoleId;
  oneLiner: string;
}

// One-liner per role — shown above the track on /learn/<role>/.
export const tracks: TrackMeta[] = [
  { role: 'claims_analyst',     oneLiner: 'Review claims with dashboards and purpose-limitation-aware queries.' },
  { role: 'fraud_analyst',      oneLiner: 'Interpret fraud-risk signals within enforcement-purpose limits.' },
  { role: 'marketing_analyst',  oneLiner: 'Build customer 360 views without unnecessary PII exposure.' },
  { role: 'finance_analyst',    oneLiner: 'Analyse cost and forecast on modelled finance marts.' },
  { role: 'operations_manager', oneLiner: 'Capacity planning on aggregated operational data.' },
  { role: 'researcher',         oneLiner: 'Run research on pseudonymised sandbox zones.' },
  { role: 'data_steward',       oneLiner: 'Govern data quality, lineage, and classifications.' },
  { role: 'data_engineer',      oneLiner: 'Build pipelines from source to mart, with tests and lineage.' },
  { role: 'platform_admin',     oneLiner: 'Operate cluster, identity, and operators — incl. break-glass.' },
];

export function trackFor(role: RoleId): TrackMeta | undefined {
  return tracks.find((t) => t.role === role);
}

export function levelMeta(id: Level): LevelMeta {
  return levels.find((l) => l.id === id)!;
}

// Stabiele module-key die door content-frontmatter en localStorage wordt gebruikt.
export function moduleKey(role: RoleId, level: Level, order: number): string {
  return `${role}/${level}/${order}`;
}
