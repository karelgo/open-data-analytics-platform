#!/usr/bin/env node
// Build-time loader: kopieert opa-policies-src/data/role_mappings.json
// naar src/data/role-mappings.generated.json zodat de Astro-build één bron
// van waarheid heeft (geen drift tussen OPA en portal-UI).
//
// Bewust een prebuild-stap i.p.v. import-buiten-root: zo blijft Astro/Vite
// fs-allow strict en geeft het bestand één duidelijke origin in dist/.

import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..', '..');
const src = resolve(repoRoot, 'opa-policies-src', 'data', 'role_mappings.json');
const destDir = resolve(__dirname, '..', 'src', 'data');
const dest = resolve(destDir, 'role-mappings.generated.json');

if (!existsSync(src)) {
  console.error(`[sync-data] Bron ontbreekt: ${src}`);
  console.error('[sync-data] Verwacht opa-policies-src/data/role_mappings.json relatief aan repo-root.');
  process.exit(1);
}

mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log(`[sync-data] ${src} -> ${dest}`);
