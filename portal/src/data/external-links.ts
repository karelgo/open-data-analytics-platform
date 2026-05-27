// External-link constants used across the portal. Centralised so a CNAME
// switch (GitHub Pages → custom domain) is a one-line change.

// Public documentation site (MkDocs Material, gebouwd door
// .github/workflows/docs.yml). Voor custom domain: pas dit aan én
// configureer de CNAME in docs/CNAME.
export const DOCS_URL = 'https://fresh-minds.github.io/FreshStackableDataPlatform/';

// Deep-link naar een specifieke architecturelaag in de docs. De anchors
// komen overeen with the stage-id's in `components.ts` (identity, ingestion,
// storage, transformation, consumption, discovery, pipeline, observability,
// agents) en with the headings in `docs/architecture/index.md`.
export function docsArchitectureUrl(stageId?: string): string {
  const base = `${DOCS_URL}architecture/`;
  return stageId ? `${base}#${stageId}` : base;
}
