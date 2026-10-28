#!/usr/bin/env node
// Build-time loader: kopieert docs/handbooks/<NN-rol>.md (source-of-truth
// per rol) naar portal/src/content/handbooks/<role-id>.md with the juiste
// frontmatter (`title`, `role`) zodat Astro's content-collection het kan
// renderen via /handbooks/<role-id>/.
//
// We dupliceren BEWUST de bestanden — de source blijft in docs/, maar de
// portal-build heeft een gebundelde kopie zodat we niet runtime van buiten
// de Astro-tree hoeven te lezen. Sync draait elke `npm run build` (zie
// package.json prebuild).
//
// Mapping (role-id → filename) komt uit roles.ts handbookPath; we extracten
// alleen de basename zodat we niet de hele roles.ts hier hoeven te imorteren.

import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..', '..');
const srcDir = resolve(repoRoot, 'docs', 'handbooks');
const destDir = resolve(__dirname, '..', 'src', 'content', 'handbooks');

// Mapping role-id → docs/handbooks/-basename. Keep in sync with
// portal/src/data/roles.ts (handbookPath).
const MAP = {
  "claims_analyst": "01-claims-analyst.md",
  "fraud_analyst": "02-fraud-analyst.md",
  "marketing_analyst": "04-marketing-analyst.md",
  "finance_analyst": "05-finance-analyst.md",
  "operations_manager": "06-operations-manager.md",
  "researcher": "08-researcher.md",
  "data_steward": "09-data-steward.md",
  "data_engineer": "10-data-engineer.md",
  "platform_admin": "11-platform-admin.md"
};

if (!existsSync(srcDir) || !statSync(srcDir).isDirectory()) {
  console.warn(`[sync-handbooks] ${srcDir} missing — skip (fresh checkout without docs/?)`);
  process.exit(0);
}

mkdirSync(destDir, { recursive: true });

let copied = 0;
let missing = 0;

for (const [roleId, filename] of Object.entries(MAP)) {
  const srcPath = resolve(srcDir, filename);
  const destPath = resolve(destDir, `${roleId}.md`);

  if (!existsSync(srcPath)) {
    missing += 1;
    console.warn(`[sync-handbooks] missing: ${srcPath} — skip`);
    continue;
  }

  const md = readFileSync(srcPath, 'utf8');

  // First H1 = title. Fallback: filename without sequence number + extension.
  const titleMatch = md.match(/^#\s+(.+)$/m);
  const title = titleMatch
    ? titleMatch[1].trim()
    : filename.replace(/^\d+-/, '').replace(/\.md$/, '').replace(/-/g, ' ');

  // Strip the first H1 from the body so the Astro page template doesn't
  // render it twice (the page renders the title from frontmatter).
  const body = titleMatch
    ? md.replace(/^#\s+.+\n+/m, '')
    : md;

  // Quote-escape title for YAML frontmatter.
  const safeTitle = title.replace(/"/g, '\\"');

  const out = `---\ntitle: "${safeTitle}"\nrole: ${roleId}\n---\n\n${body}`;
  writeFileSync(destPath, out);
  copied += 1;
}

console.log(`[sync-handbooks] ${copied} copied → ${destDir}`);
if (missing > 0) {
  console.warn(`[sync-handbooks] ${missing} missing source files`);
}
