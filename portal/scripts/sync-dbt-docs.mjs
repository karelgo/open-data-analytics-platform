#!/usr/bin/env node
// Build-time loader: kopieert dbt/target/static_index.html (één self-contained
// HTML-bundel die `dbt docs generate --static` produceert) naar
// portal/public/dbt-docs.html, zodat zowel Vite (dev) als nginx (prod) het
// statisch serveren op /dbt-docs.html.
//
// Bewust een single file (geen public/dbt-docs/index.html): Astro's dev
// server routeert /dbt-docs/ via z'n eigen pages-resolver en negeert
// public/<dir>/index.html, dus dat zou alleen in productie werken. Single
// file is identiek in dev en prod.
//
// Als de static-bundel ontbreekt (typisch op een verse checkout zonder
// `make dbt-docs`-run met live Trino), schrijven we een placeholder met
// instructies. Zo blijft de portal-build groen en is de fout uitlegbaar in de
// browser i.p.v. een 404.

import { copyFileSync, existsSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..', '..');

const src = resolve(repoRoot, 'dbt', 'target', 'static_index.html');
const destDir = resolve(__dirname, '..', 'public');
const dest = resolve(destDir, 'dbt-docs.html');

mkdirSync(destDir, { recursive: true });

// Heuristiek: een echte dbt-docs static bundle is honderden KB tot meerdere
// MB groot; de placeholder hieronder is ~1.7KB. Zo schrijven we niet per
// ongeluk een echte bundle (b.v. via COPY portal/ in Docker) over met een
// placeholder.
const PLACEHOLDER_THRESHOLD_BYTES = 50_000;

if (existsSync(src)) {
  copyFileSync(src, dest);
  console.log(`[sync-dbt-docs] ${src} -> ${dest}`);
} else if (existsSync(dest) && statSync(dest).size > PLACEHOLDER_THRESHOLD_BYTES) {
  // Source ontbreekt (typisch: Docker-build zonder dbt/ in de context), maar
  // er staat al een grote bundel op de bestemming — laat 'm staan.
  console.log(`[sync-dbt-docs] ${src} ontbreekt — bestaande ${dest} (groot bestand) wordt behouden.`);
} else {
  // Placeholder — toont een nette uitleg i.p.v. een 404. Geen externe assets,
  // past binnen de strict CSP van portal/nginx.conf.
  const placeholder = `<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>dbt docs — nog niet gegenereerd</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #14110c; color: #e8e3d5; max-width: 720px; margin: 4rem auto; padding: 0 1.5rem; line-height: 1.5; }
    h1 { color: #f59e0b; }
    code, pre { background: #1f1a10; border: 1px solid #2a2417; border-radius: 6px; padding: .15rem .35rem; font-size: .9em; }
    pre { padding: .75rem 1rem; overflow-x: auto; }
    a { color: #f59e0b; }
    .muted { color: #9a8f76; font-size: .85rem; }
  </style>
</head>
<body>
  <h1>dbt-documentatie nog niet gegenereerd</h1>
  <p>
    Deze pagina toont normaal de <strong>statisch geëxporteerde dbt docs</strong>
    (modellen, tests, sources, lineage) van het ODAP platform. De build-bundel
    <code>dbt/target/static_index.html</code> ontbreekt op het moment dat de
    portal-image gebouwd is.
  </p>
  <h2>Lokaal genereren</h2>
  <p>Vanaf de repo-root, met een bereikbare Trino:</p>
  <pre>make dbt-docs</pre>
  <p>
    Dit runt <code>dbt deps &amp;&amp; dbt docs generate --static</code> en kopieert
    de output naar <code>portal/public/dbt-docs.html</code>. Herbouw daarna
    de portal-image (of refresh in dev-mode) en deze pagina toont de docs.
  </p>
  <p class="muted">
    In productie wordt deze stap door CI of een Airflow-job uitgevoerd zodra de
    silver/gold-runs slagen. Lineage staat ook in
    <a href="https://openmetadata.odap.local:8443">OpenMetadata</a>
    via de <code>governance_om_ingest</code> DAG.
  </p>
</body>
</html>
`;
  writeFileSync(dest, placeholder);
  console.warn(`[sync-dbt-docs] ${src} ontbreekt — placeholder geschreven naar ${dest}`);
  console.warn('[sync-dbt-docs] Run `make dbt-docs` om echte dbt-documentatie te genereren.');
}
