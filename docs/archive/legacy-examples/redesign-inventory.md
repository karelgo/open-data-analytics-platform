# Portal redesign — Step 1 inventory

Audit of the existing ODAP Portal in `portal/` against the design
system in the redesign brief. The aim of this document is to enumerate
**what exists**, **where styling lives**, and **what behavior must be
preserved** before any code is touched.

This is the deliverable for **Step 1 (Audit)**. No code is changed yet.

> **Note on the reference HTML.** The brief references `refined.html` and
> `technical.html` as design exemplars. Neither file is checked in to this
> repo — only the design-system spec embedded in the brief itself is
> available. The token vocabulary, type rules, and component vocabulary in
> this inventory follow that spec literally. If `refined.html` /
> `technical.html` exist outside the repo they should be added to
> `docs/redesign-reference/` before Step 2 so the redesign can be
> visually compared against them.

---

## 1. Stack

- **Framework:** Astro 4.16 (`portal/package.json:14`), static output
  (`portal/astro.config.mjs:7`).
- **Content:** `@astrojs/mdx` for the Academy (Content Collections at
  [src/content/learn/](portal/src/content/learn/), schema in
  [src/content/config.ts](portal/src/content/config.ts:1)).
- **No UI framework** (no React/Vue/Svelte/Tailwind/shadcn/Material). All
  styling is plain CSS in `<style>` / `<style is:global>` blocks inside
  Astro components.
- **No font loader.** No `@fontsource`, no Google Fonts, no `@import`.
  The site relies on `font-family: ui-sans-serif, system-ui, -apple-system,
  "Segoe UI", Roboto, sans-serif` set in
  [Layout.astro:145](portal/src/layouts/Layout.astro:145).
- **Production runtime:** static files served by `nginx`
  ([portal/nginx.conf](portal/nginx.conf)) with a sidecar `oauth2-proxy`
  for SSO (see Section 7).
- **Strict CSP:**
  ```
  default-src 'self'; script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline'; img-src 'self' data:;
  connect-src 'self'; frame-ancestors 'none'
  ```
  ([nginx.conf:38](portal/nginx.conf:38)). **Implication:** fonts must be
  self-hosted (e.g. `@fontsource/inter`, `@fontsource/jetbrains-mono`) —
  loading from Google Fonts would require widening `style-src` and
  `font-src` to include `fonts.googleapis.com` / `fonts.gstatic.com`,
  which is a policy change beyond the scope of a visual redesign.

## 2. Layouts

| File | Purpose | Hosts global CSS? |
|---|---|---|
| [src/layouts/Layout.astro](portal/src/layouts/Layout.astro) | Shell for every page: `<head>`, topbar, footer, theme-toggle script, identity bootstrap, all base CSS variables and global rules. | **Yes** — `<style is:global>` block lines 141–241. |
| [src/layouts/LearnLayout.astro](portal/src/layouts/LearnLayout.astro) | Wraps `Layout.astro` for Academy pages. Adds module list / breadcrumb / module-prose / nav styles. | **Yes** — `<style is:global>` block lines 19–157. |

## 3. Pages

| Route | File | Notes |
|---|---|---|
| `/` | [src/pages/index.astro](portal/src/pages/index.astro) | Hero + reference-architecture diagram + lagen overzicht + rol grid. |
| `/architecture/` | [src/pages/architecture.astro](portal/src/pages/architecture.astro) | Hero + diagram + zoek/filter + per-stage card grid + data zones. |
| `/me/` | [src/pages/me.astro](portal/src/pages/me.astro) | Role-aware tools, capabilities, shortcuts, "mijn components" highlight in diagram. Renders most content client-side via JSON payload. |
| `/csv-upload/` | [src/pages/csv-upload.astro](portal/src/pages/csv-upload.astro) | Two-step wizard (MinIO upload → Airflow trigger). |
| `/go/<service>/` | [src/pages/go/[service].astro](portal/src/pages/go/[service].astro) | SSO redirect stubs (8 services). |
| `/go/minio/` | [src/pages/go/minio.astro](portal/src/pages/go/minio.astro) | Special MinIO SSO redirect (calls `/api/minio-sso/login`). |
| `/learn/` | [src/pages/learn/index.astro](portal/src/pages/learn/index.astro) | Academy overview — eindusers + platform team grids. |
| `/learn/<role>/` | [src/pages/learn/[role]/index.astro](portal/src/pages/learn/[role]/index.astro) | Per-role track (Foundation/Practitioner/Expert) with module list. |
| `/learn/<role>/<module>/` | [src/pages/learn/[role]/[module].astro](portal/src/pages/learn/[role]/[module].astro) | MDX module renderer with crumbs, lab launcher, checks block, quiz block, prev/next nav. |
| `/learn/me/` | [src/pages/learn/me.astro](portal/src/pages/learn/me.astro) | Progress table + earned-certificate list + reset button. |
| `/learn/cert/` | [src/pages/learn/cert/index.astro](portal/src/pages/learn/cert/index.astro) | Generated certificate (HTML render + SVG download). **Print-styled.** |

## 4. Shared components

### Architecture / role-aware

| Component | File | Purpose |
|---|---|---|
| `ReferenceArchitecture` | [src/components/ReferenceArchitecture.astro](portal/src/components/ReferenceArchitecture.astro) | The Monte-Carlo-style diagram. Hosts the **pastel pill swim-lanes** (Discovery / Pipeline / Observability) the brief calls out for removal. Reads from `data/components.ts`. |
| `ComponentCard` | [src/components/ComponentCard.astro](portal/src/components/ComponentCard.astro) | Card used in stage grids on `/architecture/` and (cloned in JS) on `/me/`. |
| `StageSection` | [src/components/StageSection.astro](portal/src/components/StageSection.astro) | Section header + grid of `ComponentCard`s for one stage. Cloned in JS in `me.astro`. |
| `StatusBadge` | [src/components/StatusBadge.astro](portal/src/components/StatusBadge.astro) | Pill with a status dot, driven by `data-status-job`. |

### Academy

| Component | File | Purpose |
|---|---|---|
| `TrackCard` | [src/components/learn/TrackCard.astro](portal/src/components/learn/TrackCard.astro) | Per-role card on `/learn/`. |
| `ModuleStep` | [src/components/learn/ModuleStep.astro](portal/src/components/learn/ModuleStep.astro) | Row in the module list on `/learn/<role>/`. |
| `ProgressDot` | [src/components/learn/ProgressDot.astro](portal/src/components/learn/ProgressDot.astro) | Small status glyph; class is set client-side from `learn-progress.ts`. |
| `LabLauncher` | [src/components/learn/LabLauncher.astro](portal/src/components/learn/LabLauncher.astro) | "Open in X / vscode.dev" button group inside a module. |
| `ChecksBlock` | [src/components/learn/ChecksBlock.astro](portal/src/components/learn/ChecksBlock.astro) | Auto-check list calling `/api/learn/check/<id>`. |
| `QuizBlock` | [src/components/learn/QuizBlock.astro](portal/src/components/learn/QuizBlock.astro) | Multiple-choice quiz, marks module `done` on full pass, dispatches `odap-learn:cert` when `certifies=true`. |

### Cross-cutting

- **`/me/` clones the `ComponentCard` / `StageSection` markup in JS** (lines
  [me.astro:154–197](portal/src/pages/me.astro:154)) so it can re-render
  per role without an Astro round-trip. **Any redesign of those components
  must update both the `.astro` source AND the duplicated string template
  in `me.astro`.**
- The `is:global` style blocks in `me.astro:324` and `LearnLayout.astro:19`
  exist precisely because `innerHTML`-injected nodes cannot pick up
  Astro's scoped CSS.

## 5. Tokens & colors as they exist today

The codebase already uses CSS variables — they're declared **inside the
`<style is:global>` block in `Layout.astro`** rather than in a dedicated
tokens file.

### Existing tokens — Layout.astro:142–180

```
--radius:       6px
--max-w:        1280px

# Dark (default)
--c-bg          #0e1116
--c-panel       #161b22
--c-panel-2     #1f262d
--c-border      #30363d
--c-text        #e6edf3
--c-muted       #9ba6b1
--c-accent      #f59e0b   ← UWV orange
--c-accent-2    #fbbf24
--c-link        #79c0ff
--c-ok          #3fb950
--c-warn        #d29922
--c-bad         #f85149

# Light
--c-bg          #f7f8fa
--c-panel       #ffffff
--c-panel-2     #eef1f5
--c-border      #d0d7de
--c-text        #1f2328
--c-muted       #57606a
--c-accent      #b45309
--c-accent-2    #92400e
--c-link        #0969da
--c-ok          #1a7f37
--c-warn        #9a6700
--c-bad         #cf222e
```

Mapping to the redesign vocabulary (section "Color tokens (light)" in the
brief):

| Brief token   | Closest current var | Mapping note |
|---|---|---|
| `--bg`        | `--c-bg`          | Renaming + warmer hue (`#FAFAF7` vs cool `#f7f8fa`). |
| `--bg-elev`   | `--c-panel`       | Was `#ffffff` — keep. |
| `--bg-sunken` | `--c-panel-2`     | Was `#eef1f5` — switch to warm `#F2F1EB`. |
| `--ink-1..5`  | `--c-text` / `--c-muted` (only 2 levels) | **Extension required** — current palette has 2 ink levels, redesign needs 5. |
| `--line`, `--line-soft` | `--c-border` | Need to split into two strengths. |
| `--accent`    | `--c-accent`      | Current is `#b45309` (light) / `#f59e0b` (dark). Brief asks for `oklch(0.55 0.14 50)` — visually aligned, swap is safe. |
| `--accent-soft` | (none)         | New. |
| `--status-ok/warn/down` | `--c-ok / warn / bad` | Direct rename. |
| `--cat-discovery / pipeline / observability / identity` | bespoke values inside `ReferenceArchitecture.astro:251–257` | New, replacing today's `#d946ef / #8b5cf6 / #f59e0b / #f87171 / #38bdf8 / #34d399`. |

The redesign also wants **dark tokens for technical surfaces** — today
the entire app uses one dark palette. We do not yet have any "technical
dashboard" surface that needs the dark vocabulary; once the home /
architecture / me pages are token-driven, the dark side comes for free
via `[data-theme="dark"]`.

## 6. Hard-coded literals (the things that must move into tokens)

### 6.1 Colors not behind a variable — **must be moved**

| File:line | Literal | Where used | Action |
|---|---|---|---|
| [Layout.astro:209](portal/src/layouts/Layout.astro:209) | `#1a1206` | `.who-role` text on accent bg | Replace with token (e.g. `--ink-on-accent`) — same color is repeated 4 more times below. |
| [Layout.astro:210](portal/src/layouts/Layout.astro:210) | `#fff` | light-theme override of the same | Same fix. |
| [index.astro:99](portal/src/pages/index.astro:99) | `#1a1206` | `.btn-primary` text on accent | Replace via shared `.btn--primary` once primitives exist. |
| [csv-upload.astro:213](portal/src/pages/csv-upload.astro:213) | `#1a1206` | `.btn-primary` text on accent | idem. |
| [csv-upload.astro:217](portal/src/pages/csv-upload.astro:217) | `#fff` | light-theme `.btn-primary` text | idem. |
| [QuizBlock.astro:57](portal/src/components/learn/QuizBlock.astro:57) | `#1a1206` | quiz submit button text | idem. |
| [QuizBlock.astro:62](portal/src/components/learn/QuizBlock.astro:62) | `#fff` | light-theme override | idem. |
| [ReferenceArchitecture.astro:251–257](portal/src/components/ReferenceArchitecture.astro:251) | `#d946ef`, `#8b5cf6`, `#f59e0b`, `#38bdf8`, `#34d399`, `#f87171` | `--c-discovery / pipeline / observability / sources / output / identity` | These are scoped vars; **move to global category-hue tokens** in the new tokens file with the OKLCH values from the brief. |
| [learn/cert/index.astro:51–101](portal/src/pages/learn/cert/index.astro:51) | `#fdfdf8`, `#1a1206`, `#d0c8b0`, `#8b5a00`, `#5b4520`, `#8a7d62` | parchment-style certificate | **Keep local.** This is an intentional standalone "paper" surface (printable, downloadable as standalone SVG) — outside the app's chrome. Document it as an exception. |
| [learn/cert/index.astro:60](portal/src/pages/learn/cert/index.astro:60) | `rgba(0,0,0,.08)` | certificate paper drop-shadow | Keep local — same exception. |
| [learn/cert/index.astro:206–219](portal/src/pages/learn/cert/index.astro:206) | hex literals inside generated SVG | Standalone SVG download — must remain self-contained, no CSS variables possible. **Keep, but mark as locked.** |

### 6.2 `--radius: 6px` is the only radius token — brief asks for 5

Today's single `--radius: 6px` ([Layout.astro:143](portal/src/layouts/Layout.astro:143)) is reused for ~25 components. Brief wants 6/10/14/20/999. Inline `border-radius: 999px` already appears (badges, chips, role-card cat tag), `border-radius: 50%` for status dots, `border-radius: 6px` (literal) and `border-radius: 2px` (`pdot` in `LearnLayout.astro:67`) and `border-radius: 4px` (code background in `Layout.astro:190`). All of those need to point at named tokens.

### 6.3 Spacing — no token system today

Spacing is fully literal across all components: `0.15rem / 0.25rem / 0.35rem / 0.45rem / 0.5rem / 0.55rem / 0.65rem / 0.75rem / 0.85rem / 0.9rem / 1rem / 1.25rem / 1.5rem / 2rem / 2.5rem`. ~150 occurrences across the 20 source files. Brief specifies a 4 px scale (4 / 8 / 10 / 14 / 18 / 22 / 28 / 32 / 40 / 48 / 60 / 80) — these need to become `--space-*` tokens.

### 6.4 Typography — no scale yet

- Font sizes appear as `0.65rem` through `1.75rem` in 60+ places.
- No mono / sans split: every page uses the system sans stack and only
  `code` / `<pre>` get `ui-monospace, SFMono-Regular, Menlo, monospace`
  ([Layout.astro:190](portal/src/layouts/Layout.astro:190)).
- `letter-spacing` is hardcoded per component (`0.05em / 0.06em / 0.07em / 0.08em`).
- The brief calls for **Inter** (sans) and **JetBrains Mono** (mono) with
  specific weights, plus an italic serif accent on the hero h1. None of
  this exists yet.

### 6.5 Brand mark

The current "brand" in the topbar is plain text:

```html
<a class="brand" href="/">UWV <span>Platform Portal</span></a>
```

— [Layout.astro:57](portal/src/layouts/Layout.astro:57). The brief asks
for a 26 px rounded square in accent color with white "UWV" text + a
sans-serif wordmark next to it. **No SVG logo asset exists yet** — needs
to be created (inline SVG, no new dep).

### 6.6 Font loading approach (proposed)

Add as devDependencies (already-present `astro` toolchain handles bundling):
`@fontsource-variable/inter` and `@fontsource-variable/jetbrains-mono`.
Self-hosted, no CSP change. Imported once from the tokens entrypoint
(see Section 9). If the user objects to two new deps we can fall back to
shipping a `.woff2` pair in `public/fonts/` and `@font-face`-ing them by
hand.

## 7. Behavior that MUST be preserved

Anything in this list breaks production if a redesign drops it. The
visual layer must be rebuilt around it, not over it.

### 7.1 Auth / identity

- `<script>` in [Layout.astro:92–112](portal/src/layouts/Layout.astro:92)
  calls `/oauth2/userinfo` (oauth2-proxy sidecar), reads
  `me.groups | me.roles`, picks the first known role, persists it in
  `sessionStorage` under `odap-portal-role` / `odap-portal-user`, and
  re-renders the topbar `[data-who]` slot.
- Logout link is dynamically built and routes via `/oauth2/sign_out` with
  a Keycloak `post_logout_redirect_uri` that switches between
  `odap.local` and `odap-platform.cloud` based on hostname.
- **Preserve:** the `[data-who]` element, the `.who / .who-role / .who-user / .who-logout` class hooks (renamed is fine, but the JS that writes them must be updated in lock-step), the `sessionStorage` keys, the `/oauth2/userinfo` and `/oauth2/sign_out` endpoints.

### 7.2 Theme toggle

- Pre-paint script in [Layout.astro:18–28](portal/src/layouts/Layout.astro:18)
  reads `localStorage['odap-portal-theme']` (or falls back to
  `prefers-color-scheme: light`) and sets
  `document.documentElement.dataset.theme` **before** body paint to
  avoid flash-of-wrong-theme.
- Toggle button uses `[data-theme-toggle]` attribute selector
  ([Layout.astro:64](portal/src/layouts/Layout.astro:64)) and flips
  `data-theme` between `dark` / `light`.
- **Preserve:** the `localStorage` key `odap-portal-theme`, the
  pre-paint script, the `data-theme` attribute switching mechanism, and
  the icon-based toggle (sun/moon SVGs swapped via CSS). Dark must
  remain the default for unauthenticated visitors.

### 7.3 Cross-environment URL rewrite

- [Layout.astro:34–51](portal/src/layouts/Layout.astro:34) — runs on every
  page, rewrites `odap.local` → `odap-platform.cloud` whenever
  hostname ends with `.odap-platform.cloud`. Uses a `MutationObserver` so
  links injected by client-side JS (e.g. `/me/`, `/architecture/` status
  refresh) get rewritten too.
- **Preserve as-is** — must be in `Layout.astro` `<head>` and run before
  any page-level script.

### 7.4 Status fetch

- Three pages (`/`, `/architecture/`, `/me/`) each have an identical
  `refreshStatus()` function on a 30 s `setInterval`. They iterate
  `[data-status-job]` and call `/api/status/up?job=…`, then add
  `.ok / .warn / .bad` classes to the dot.
- The endpoint is implemented by nginx
  ([nginx.conf:54–75](portal/nginx.conf:54)) — proxies an instant
  Prometheus query and returns 200 with `{status:"unavailable"}` if
  Prometheus is down.
- **Preserve:** the `[data-status-job]` attribute, the `.dot` element
  inside it, the three CSS state classes (`ok / warn / bad`), the 30 s
  refresh cadence. The duplicated `refreshStatus()` is a candidate for
  extraction into `src/scripts/`, but doing so is **out of scope** for
  Step 2 (tokens) and **in scope** for Steps 5–7.

### 7.5 Role gating on `/me/`

- Capabilities come from
  [src/data/role-mappings.generated.json](portal/src/data/role-mappings.generated.json),
  which is **regenerated at build time** from
  `opa-policies-src/data/role_mappings.json` by
  [scripts/sync-data.mjs](portal/scripts/sync-data.mjs) (see
  `package.json:9`). Don't manually edit the generated JSON.
- `me.astro` injects the full payload as JSON in a `<script type="application/json">`,
  then renders client-side based on URL `?role=<id>` or `sessionStorage`.
- **Preserve:** the JSON payload shape, the `data-component` markers used
  for the per-role highlight pass on `.ref-arch`, the `.is-mine` class
  added to highlighted tiles.

### 7.6 Academy progress

- [src/scripts/learn-progress.ts](portal/src/scripts/learn-progress.ts) —
  `localStorage['odap-learn-progress']`, optional sync to
  `/api/learn/progress` (Academy backend sidecar; nginx falls through to
  503 if not running).
- `[data-progress-key]` on every `ProgressDot` and `[data-track-progress]`
  on every `TrackCard` are read by `renderDots()` in the script.
- Quiz pass dispatches `document` event `odap-learn:cert` with
  `{detail:{key}}`.
- Module progress event: `odap-learn:progress`.
- **Preserve:** the localStorage key, the data attributes, the two custom
  events, the `.pdot.done / .pdot.in-progress` class hooks (rename is
  fine but coordinate with `learn-progress.ts:50–63` and
  `learn-cert/index.astro` `isComplete()` which inspects all keys
  starting with `<roleId>/`).

### 7.7 CSV-upload wizard

- Source list is rendered into `<option data-*>` attributes
  ([csv-upload.astro:48](portal/src/pages/csv-upload.astro:48)) and read
  client-side. **No backend** — it just builds MinIO and Airflow URLs.
- **Preserve:** the `<option data-bucket / data-prefix / data-dag / data-desc>`
  contract, the IDs the script writes into (`src-desc`, `src-bucket`, …
  `dag-conf`, `mc-cmd`), and the `<a id="open-minio">` / `<a id="open-airflow">`
  hooks.

### 7.8 Generated certificate

- Self-contained "paper" aesthetic — explicitly out-of-band from the rest
  of the design system. Cream/parchment colors are intentional. Print
  styles override `topbar`, `footer`, etc.
- **Preserve:** standalone styling (we'll mark this as an exception in
  the tokens file), the SVG download flow, the print media query, the
  `cert-` ID hash format.

### 7.9 Routes / data shapes

- All component URLs (`https://*.odap.local:8443`) are **build-time
  constants** in [src/data/components.ts](portal/src/data/components.ts:62).
  Do not change them without re-checking the cross-env rewrite in 7.3.
- 11 role IDs are pinned in [src/data/roles.ts:7–18](portal/src/data/roles.ts:7)
  and duplicated in [src/content/config.ts:9–21](portal/src/content/config.ts:9)
  and [Layout.astro:98–102](portal/src/layouts/Layout.astro:98). **Don't
  rename role IDs** — they index the OPA policies.

## 8. What the brief explicitly removes

- The pastel pill swim-lanes (Discovery / Pipeline / Observability) — implemented in [ReferenceArchitecture.astro:36–57, 180–225](portal/src/components/ReferenceArchitecture.astro:36) with CSS at `.ref-overlay / .overlay-top / .overlay-bottom-1 / .overlay-bottom-2`. Replace with the swim-lane row pattern (168 px label column + 4-column tile grid + hairline rules + mono → arrows).
- The orange-filled `.btn-primary` + black-outline `.btn` ([index.astro:94–99](portal/src/pages/index.astro:94), repeated at [csv-upload.astro:200–218](portal/src/pages/csv-upload.astro:200)). Replace with `.btn / .btn--primary / .btn--accent` per the brief, accent reserved for **one CTA per screen**.
- System-font stack ([Layout.astro:145](portal/src/layouts/Layout.astro:145), [Layout.astro:190](portal/src/layouts/Layout.astro:190)). Replace with Inter + JetBrains Mono via `@fontsource`.
- Hard-coded category hex values in `ReferenceArchitecture.astro:251–257`. Move to global category-hue tokens.
- Per-component hardcoded radii / spacing / font sizes — all of these become token references.

## 9. Step 2 — what landed

Two new style files at [portal/src/styles/](portal/src/styles/) plus
font self-hosting via @fontsource:

```
portal/src/styles/
  tokens.css   # full token vocabulary + --c-* legacy aliases
  base.css     # box-sizing, body font, antialiasing, focus ring,
               # .mono / .tabular-nums utilities
```

(Dropped the separate `fonts.css` — npm-style imports of @fontsource
packages from `Layout.astro` frontmatter are clearer than a CSS-import
shim.)

Imports wired once in [Layout.astro:2–5](portal/src/layouts/Layout.astro:2):

```astro
---
import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';
import '../styles/tokens.css';
import '../styles/base.css';
---
```

### Tokens (tokens.css)

- **Surface palettes.** Dark (`:root, [data-theme="dark"]`) and light
  (`[data-theme="light"]`) — each defines `--bg / --bg-elev / --bg-sunken`,
  five-step ink scale `--ink-1..5`, two-step lines `--line / --line-soft`,
  brand (`--accent / --accent-soft / --accent-ink`), three status
  colors, and `--card-shadow-hover`. `color-scheme` set per theme.
- **Categories** (`--cat-discovery / pipeline / observability / identity`)
  with `-soft` and `-line` variants — for the future swim-lane
  redesign in Step 5.
- **Paper surface** (`--paper-bg / line / ink-1 / ink-2 / ink-3 / accent`) —
  certificate palette folded into the system per the user decision in §10.
- **Spacing scale** `--space-1..12` (4 / 8 / 10 / 14 / 18 / 22 / 28 / 32 / 40 / 48 / 60 / 80 px).
- **Radii** `--radius-sm / md / lg / xl / pill` (6 / 10 / 14 / 20 / 999 px).
- **Type tokens**: `--font-sans` (Inter Variable), `--font-mono`
  (JetBrains Mono Variable), `--font-serif`; nine sizes from
  `--text-display` (56 px) to `--text-micro` (10 px); five weights;
  four line-heights; four letter-spacings.
- **Legacy `--c-*` aliases**: 11 aliases mapping the old vocabulary
  onto new tokens (e.g. `--c-bg → var(--bg)`, `--c-text → var(--ink-1)`,
  `--c-accent → var(--accent)`). Defined once on `:root`; theme
  overrides cascade through `var()` at use-site. `--c-link` is the
  exception (no new equivalent) and is set per theme.

### Base (base.css)

- Universal `box-sizing: border-box`.
- `html, body { background: var(--bg); color: var(--ink-1); }`.
- Body wired to `var(--font-sans)` with Inter font features + smoothing.
- `p { text-wrap: pretty; }` for orphan-balanced paragraphs.
- `.mono` and `.tabular-nums` utilities (apply `font-feature-settings: 'tnum'`).
- `:focus-visible` ring in `--accent`.

### Layout.astro changes

- Frontmatter now imports the four CSS dependencies above.
- Removed the inline `:root` token block, the
  `:root, [data-theme="dark"]` block, and the `[data-theme="light"]`
  block (122 lines of duplicated tokens — now sourced from `tokens.css`).
- Removed the `* { box-sizing }` and `html, body { margin/padding }`
  resets (now in `base.css`).
- Updated the inline `code` rule's font-family from the literal
  `ui-monospace, SFMono-Regular, Menlo, monospace` stack to
  `var(--font-mono)` so JetBrains Mono actually applies to inline code.
- Topbar / footer / panel / badge / nav / who / theme-toggle / grid
  styles **kept as-is** — they reference `--c-*` aliases which now
  resolve to the new tokens via the legacy mapping.

### What's visible to the user after Step 2

- **Body font** swaps from the system sans stack to Inter Variable.
- **Inline `code`** swaps to JetBrains Mono Variable.
- **Color tokens** shift toward warm palette: `--c-bg` from `#0e1116`
  cool-charcoal → `#14130E` warm-charcoal in dark; from `#f7f8fa` cool
  off-white → `#FAFAF7` warm off-white in light. Other surface colors
  follow the same warming.
- **Accent** shifts from `#f59e0b` (dark) / `#b45309` (light) to a
  single `oklch(0.55 0.14 50)` across themes — visually similar but
  more consistent.
- **Status colors** shift to OKLCH equivalents (within ~1 JND of the
  prior values).
- All component layouts unchanged. No component CSS edited.

### Verification

`npm install && npm run build` succeeds, all 60 pages built, 12 Inter
woff2 + 5 JetBrains Mono woff2 bundled into `dist/_astro/`. CSP is not
widened (fonts served from `'self'`).

## 11. Steps 3–9 — what landed after Step 2

### Step 3 — Primitives

Seven new components in [portal/src/components/primitives/](portal/src/components/primitives/):
[Button.astro](portal/src/components/primitives/Button.astro) (default / primary / accent variants, mono arrow trail), [Eyebrow.astro](portal/src/components/primitives/Eyebrow.astro) (with optional rule prefix), [StatusDot.astro](portal/src/components/primitives/StatusDot.astro) (preserves the legacy `.ok / .warn / .bad` class hooks so `src/scripts/status.ts` keeps working), [Tag.astro](portal/src/components/primitives/Tag.astro) (sans + mono variants, status tones), [NavLink.astro](portal/src/components/primitives/NavLink.astro), [Tile.astro](portal/src/components/primitives/Tile.astro) (28 px logo + name + sub-label + status, preserves `[data-component]` hook), [UserPill.astro](portal/src/components/primitives/UserPill.astro) (empty shell — markup mirrored in Layout.astro's `renderWho()`).
A live reference at [/styleguide/](portal/src/pages/styleguide.astro) shows every variant; useful when reviewing in dark + light. Linked from the footer.

### Step 4 — App shell

Redesigned topbar in [Layout.astro](portal/src/layouts/Layout.astro): 26 px accent brand mark, `<b>Platform</b> Portal` wordmark, NavLinks with active-state derived from `Astro.url.pathname`, 32 px bordered theme toggle (icon swaps via `data-theme`), UserPill on the right. The `renderWho()` template literal updated to match `UserPill`'s loaded structure (avatar with initial + role + email + ↗ logout). Footer rebuilt with mono left + ink-3 right layout. Sticky topbar with backdrop-filter for blur. All preserved JS hooks (`[data-who]`, `[data-theme-toggle]`, theme pre-paint, identity loader, `.local`→`.cloud` rewrite) untouched.

### Step 5 — Home + diagram

[scripts/status.ts](portal/src/scripts/status.ts) extracts the triplicated `refreshStatus()` into a shared module imported from each page. [ReferenceArchitecture.astro](portal/src/components/ReferenceArchitecture.astro) completely rewritten as horizontal swim-lane rows: 168 px label column with mono eyebrow + Dutch stage name + optional mono tags, 1px hairlines between lanes, mono → connector arrows between adjacent tiles in pipeline-step lanes only, soft category-tinted backgrounds for the four cross-cutting lanes (discovery / pipeline / observability / identity). Pastel pill chrome removed. [data/components.ts](portal/src/data/components.ts) gained `category` and `tags` on `StageMeta`. [pages/index.astro](portal/src/pages/index.astro) rebuilt around the editorial hero spec: 56 px display h1 with one italic serif accent in `--ink-3`, 56 ch lead, single accent CTA ("Naar mijn workspace") + two ghost buttons, mono disclaimer with status dot, 380 px live-status side card with 6 representative services. Four numbered sections below.

### Step 6 — Architecture

[pages/architecture.astro](portal/src/pages/architecture.astro) rebuilt: editorial hero (44 px), embedded swim-lane diagram, search/filter toolbar with mono `/` prefix (focus ring on `:focus-within`), per-stage detail sections, data zones row. [components/StageSection.astro](portal/src/components/StageSection.astro) and [components/ComponentCard.astro](portal/src/components/ComponentCard.astro) refreshed: eyebrow-led headers with category coloring, 36 px logo squares on `--bg-sunken`, status dot in the card head, mono stage tag in the footer.

### Step 7 — Mijn workspace

[pages/me.astro](portal/src/pages/me.astro) rebuilt with the same vocabulary. The capability list is now a key/value table on `--bg-elev` (mono uppercase keys + ink-1 values + status-coloured ja/nee). Shortcuts are restructured 36 px-icon cards. The role-architecture diagram inherits the new swim-lane look. The JS string templates (`renderToolCard`, `renderStageGroup`) were rewritten to mirror the new ComponentCard / StageSection markup verbatim, so client-side-injected tool cards look identical to server-rendered ones.

### Step 9 — Polish

- **Cert tokenized.** [pages/learn/cert/index.astro](portal/src/pages/learn/cert/index.astro) now consumes `--paper-bg / paper-line / paper-ink-1..3 / paper-accent` instead of hardcoded hex. The HTML render uses serif body for the parchment feel, mono for the cert-id. The standalone SVG download still bakes the same hex literals (a downloadable SVG can't reference CSS variables) — flagged with a "must match" comment in tokens.css. The empty / no-cert state uses the new `.state .state--error` pattern.
- **CSV upload restyled.** [pages/csv-upload.astro](portal/src/pages/csv-upload.astro) rebuilt as four numbered steps (Bron · 01 Upload · 02 Trigger · 03 Resultaat) with editorial hero, Button primitives, mono-keyed metadata rows, and tokened `<pre>` blocks. The accent CTA is reserved for "Open MinIO Console" — the start-of-flow action.
- **Academy.** Inline accent-button hex (`#1a1206`) in [components/learn/QuizBlock.astro](portal/src/components/learn/QuizBlock.astro) replaced with `var(--accent-ink)`. LearnLayout-wide styles untouched (already token-aligned via the legacy `--c-*` aliases).
- **States.** New global `.state` / `.state--error` / `.state--loading` / `.skeleton` utility classes in [styles/base.css](portal/src/styles/base.css) with reduced-motion handling, ready for any page that needs an empty / loading / error pattern. Styleguide updated with examples.

### Step 8 — Dark / technical

Skipped per the user's decision: `data-theme="dark"` continues to serve as both default theme and the technical aesthetic. The dark vocabulary in tokens.css already covers it; no separate `data-surface="technical"` introduced.

## 12. Verification (final)

`npm run build` builds 61 pages clean (added [/styleguide/](portal/src/pages/styleguide.astro)). All preserved JS hooks accounted for via grep:
`data-status-job`, `data-component`, `data-who`, `data-theme-toggle`,
`data-arch-host`, `data-active-role`, `data-progress-key` — 31 occurrences across 31 `.astro` files, all intact.

## 13. Follow-up work / TODO

- **Migration of `--c-*` aliases.** Most components now use the new tokens directly; legacy `--c-*` aliases remain in [tokens.css](portal/src/styles/tokens.css) for the LearnLayout module-prose styles, the `.panel / .badge / .grid-2 / .grid-3` legacy chrome in Layout.astro, and a few smaller surfaces. Once those are migrated, the alias block at the bottom of tokens.css can be deleted.
- **Layout.astro legacy chrome.** `.panel`, `.grid-2`, `.grid-3`, `.badge` are kept globally for the Academy pages that still rely on them. A future pass can extract `.badge` into a new primitive (already partly covered by `Tag`), and replace `.panel` with explicit section markup per page.
- **Stage tags.** `tags` field added to `StageMeta` (BATCH / STREAM / LAKEHOUSE / POLICY / QUERY) — used for the swim-lane label column. The category lanes deliberately have no tags; refine the taxonomy once the data team has a stronger opinion on what each tag means.
- **Status card on hero.** Currently shows 6 hand-picked services. Could become a dynamic "anything that's not OK" view if the live response shape is firmed up server-side.
- **Active nav state.** `Astro.url.pathname` works for static pages but the dynamic `/learn/[role]/[module]/` routes don't get an active state on the parent "Academy" link by default — verify on a few module pages.

## 10. Decisions (resolved)

1. **Reference HTML.** Work from the spec embedded in the brief; no
   external `refined.html` / `technical.html` to compare against.
2. **Two new deps.** Approved. `@fontsource-variable/inter` and
   `@fontsource-variable/jetbrains-mono` added in Step 2.
3. **`/learn/cert/`.** Folded into the design system. The cert palette
   is now exposed as `--paper-*` tokens in `tokens.css` (Section 9
   below). Step 9 (polish) refactors the cert to consume them; the
   standalone SVG generator continues to bake the same hex values
   verbatim because a downloadable SVG cannot reference CSS variables.
4. **Dark / technical surfaces.** Mapped directly to `data-theme="dark"`.
   No separate `data-surface="technical"` for now. Dark stays the
   default theme (matches today's pre-paint script behavior).
5. **One accent per screen.** Each redesigned screen will have at most
   one `.btn--accent`. The canonical CTA per screen will be picked when
   that screen is redesigned (Steps 5–8). Other links / "ghost" buttons
   become `.btn` or `.btn--primary` (ink-on-ink).
