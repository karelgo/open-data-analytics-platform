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
  { role: 'claims_analyst',     oneLiner: 'Compare daily observed demand across six overlapping domains.' },
  { role: 'fraud_analyst',      oneLiner: 'Review source coverage, completeness and duplicate observations.' },
  { role: 'marketing_analyst',  oneLiner: 'Explore technologies, skills and employer demand in advertised roles.' },
  { role: 'finance_analyst',    oneLiner: 'Compare reported salaries with original units and coverage visible.' },
  { role: 'operations_manager', oneLiner: 'Monitor daily snapshots and distinguish coverage changes from market changes.' },
  { role: 'researcher',         oneLiner: 'Study contact-redacted observations and preserve provenance and uncertainty.' },
  { role: 'data_steward',       oneLiner: 'Own job definitions, source provenance, quality tests and classifications.' },
  { role: 'data_engineer',      oneLiner: 'Operate extraction, Spark Bronze and tested dbt Silver and Gold models.' },
  { role: 'platform_admin',     oneLiner: 'Operate service health, identity and authorization for the daily pipeline.' },
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
