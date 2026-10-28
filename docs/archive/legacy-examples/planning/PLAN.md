# Generic Rebrand Plan — UWV Reference Platform → Open Data & Analytics Platform (ODAP)

**Branch:** `feat/generic-rebrand-odap`
**Goal:** Strip all UWV-specific branding, translate everything to English, and re-present this codebase as a vendor-neutral reference implementation of a modern data & analytics platform.

---

## 1. Confirmed decisions

| Question | Decision |
|---|---|
| New platform name | **Open Data & Analytics Platform** (short form: **ODAP**) |
| Compliance frameworks | Replace NORA → **SOC 2**, AVG → **GDPR**, BIO/BIO2 → **ISO 27001/27002**. Keep NIS2 and AI Act (already EU-wide). |
| Hostnames / cloud IDs | All real hostnames become `example.com` placeholders; StackIT project IDs / Azure account specifics become `<your-project-id>` placeholders. |
| Demo data scenarios | Re-theme from UWV welfare domain (WIA/WW/Wajong/ZW) to generic **customer / order / event / claim** domain. |

---

## 2. Scope summary (from codebase audit)

- **587 files** contain `UWV` references (~4,952 lines).
- **5 Kubernetes namespaces** use `uwv-` prefix; `uwv-platform` alone is referenced in ~1,017 places.
- **8 hostnames** use `*.uwv-platform.local`.
- **~30 Kubernetes labels** use `uwv.nl/*` prefix.
- **15 files** have `uwv` in their filename.
- **Logo SVG** (`portal/public/uwv-data-platform.svg`) carries "UWV Reference Data- & Analyseplatform" title.
- **Keycloak realm** named `uwv` with 11 mock users at `@uwv-platform.local`.
- **~3,000 lines of Dutch documentation** across 12 role-handbooks + 2 root-level compliance docs.
- **12 personas** (5 technical + 7 Dutch-government domain personas).
- **dbt models** for WW/WIA/Wajong/ZW/CRM/Klantcontact/FEZ schemas.
- **S3 buckets** with `uwv-` prefix: bronze/silver/gold/raw/staging/checkpoints/meta.

---

## 3. Naming dictionary

### 3.1 Platform identifiers

| Old | New |
|---|---|
| "UWV Reference Data Platform" / "UWV Reference Data- & Analyseplatform" | **Open Data & Analytics Platform** |
| "UWV Platform Portal" | **ODAP Portal** |
| `uwv-platform` (npm package) | `odap-platform` |
| `uwv_data_platform` (dbt project) | `odap_data_platform` |

### 3.2 Kubernetes

| Old | New |
|---|---|
| Namespace `uwv-platform` | `odap-platform` |
| Namespace `uwv-data` | `odap-data` |
| Namespace `uwv-meta` | `odap-meta` |
| Namespace `uwv-monitoring` | `odap-monitoring` |
| Namespace `uwv-auth` | `odap-auth` |
| Label prefix `uwv.nl/*` | `odap.io/*` |
| Cert issuer `uwv-platform-issuer` | `platform-issuer` |
| Trino cluster `uwv-trino` | `trino` |
| Hive service `uwv-hive` | `hive` |
| OpenSearch service `opensearch-uwv` | `opensearch` |

### 3.3 Hostnames & domains

| Old | New |
|---|---|
| `*.uwv-platform.local` (k3d/dev) | `*.odap.local` |
| `freshstackable.com` (public) | `example.com` |
| `eu-sovereigndataplatform.com` | `example.com` |
| `@uwv.nl` (emails) | `@example.com` |
| `@uwv-platform.local` (mock users) | `@odap.local` |
| Mock domain `odap.local` | (canonical local-dev domain) |

### 3.4 Docker images

| Old | New |
|---|---|
| `uwv-platform/portal:dev` | `odap/portal:dev` |
| `uwv-platform/jupyter-kernel:dev` | `odap/jupyter-kernel:dev` |
| `uwv-platform/nanitics-observatory:dev` | `odap/nanitics-observatory:dev` |
| `uwv-platform/multica-daemon:dev` | `odap/multica-daemon:dev` |
| `uwv-platform/portal-airflow-bridge:dev` | `odap/airflow-bridge:dev` |
| `uwv-platform/om-access-bridge:dev` | `odap/om-access-bridge:dev` |
| `uwv/dbt-trino:1.9.0-uwv` | `odap/dbt-trino:1.9.0` |

> Note: "Nanitics" and "Multica" are preserved as product names (per user direction). Only the registry prefix changes.

### 3.5 Database / storage

| Old | New |
|---|---|
| Postgres user `uwvplatform` | `odap` |
| Postgres password (dev) `uwv-dev-only-CHANGE-ME-2026` | `odap-dev-only-CHANGE-ME` |
| S3 bucket `uwv-bronze` | `bronze` |
| S3 bucket `uwv-silver` | `silver` |
| S3 bucket `uwv-gold` | `gold` |
| S3 bucket `uwv-raw` | `raw` |
| S3 bucket `uwv-staging` | `staging` |
| S3 bucket `uwv-checkpoints` | `checkpoints` |
| S3 bucket `uwv-meta` | `metadata` |
| Schema pattern `bronze.uwv.<entity>` | `bronze.<domain>.<entity>` (domain = `customers`, `orders`, etc.) |

### 3.6 Auth & policy

| Old | New |
|---|---|
| Keycloak realm `uwv` | `odap` |
| Realm file `realm-uwv.json` | `realm.json` |
| OPA data `uwv_role_mappings.json` | `role_mappings.json` |
| OPA policy `trino-uwv-roles.rego` | `trino-roles.rego` |
| Env var prefix `UWV_*` (16 vars) | Remove prefix (e.g. `UWV_BRONZE_BUCKET` → `BRONZE_BUCKET`) |

### 3.7 dbt

| Old | New |
|---|---|
| Project name `uwv_data_platform` | `odap_data_platform` |
| Profile `uwv_trino` | `trino` |
| Macro `ensure_uwv_schemas()` | `ensure_schemas()` |
| Env var `UWV_PSEUDONYMIZE_SALT` | `PSEUDONYMIZE_SALT` |

### 3.8 Python / portal

| Old | New |
|---|---|
| Python package `uwv_lab` | `odap_lab` |
| sessionStorage key `uwv-portal-role` | `odap-portal-role` |
| Event names `uwv-learn:*` | `odap-learn:*` |
| Logo file `uwv-data-platform.svg` | `odap-logo.svg` |
| Default repo `github.com/UWV/UDP_Stackable` (placeholder in code) | `github.com/<your-org>/odap` |

### 3.9 Files to rename (git mv)

| Old | New |
|---|---|
| `uwv-platform-master-agent-prompt-v2.md` | `master-agent-prompt.md` |
| `uwv-platform-adr-0002-iceberg-vs-delta.md` | `adr-0002-iceberg-vs-delta.md` |
| `referentiearchitectuur-uwv-data-analytics.md` | `reference-architecture.md` |
| `requirements-compliant-data-analyseplatform.md` | `requirements.md` |
| `uwv-platform-mapping-research.md` | `platform-mapping-research.md` |
| `infrastructure/helm/keycloak/realm-uwv.json` | `infrastructure/helm/keycloak/realm.json` |
| `infrastructure/azure/vpn-client/uwv-platform-vpn-client.pfx` | `infrastructure/azure/vpn-client/platform-vpn-client.pfx` |
| `platform/10-opa/policies/trino-uwv-roles.rego` | `platform/10-opa/policies/trino-roles.rego` |
| `platform/13-openmetadata-config/classifications-uwv.yaml` | `platform/13-openmetadata-config/classifications.yaml` |
| `platform/14-monitoring/pdb-uwv.yaml` | `platform/14-monitoring/pdb.yaml` |
| `platform/14-monitoring/prometheusrule-uwv.yaml` | `platform/14-monitoring/prometheusrule.yaml` |
| `dbt/macros/ensure_uwv_schemas.sql` | `dbt/macros/ensure_schemas.sql` |
| `opa-policies-src/trino/trino-uwv-roles.rego` | `opa-policies-src/trino/trino-roles.rego` |
| `opa-policies-src/trino/trino-uwv-roles_test.rego` | `opa-policies-src/trino/trino-roles_test.rego` |
| `opa-policies-src/data/uwv_role_mappings.json` | `opa-policies-src/data/role_mappings.json` |
| `portal/public/uwv-data-platform.svg` | `portal/public/odap-logo.svg` |
| `docs/handleidingen/` (folder, 13 NL files) | `docs/handbooks/` (folder, English files) |
| `freshstackable-contact.json` | (keep — already neutral) |

---

## 4. Persona redesign

### 4.1 Old persona set (12 total, mix of NL government + technical)

Technical: Data Engineer, Data Analyst, Data Steward, Researcher, Platform Admin
Domain: WIA-beoordelaar, WW-handhaver, Wajong arbeidsdeskundige, CRM-medewerker, FEZ-analist, SMZ-planner, Proactief dienstverlener

### 4.2 New persona set (9 total: 5 technical + 4 business)

| Persona | Initials | Role |
|---|---|---|
| Data Engineer | DE | Build pipelines, manage ingestion |
| Data Analyst | DA | Build dashboards, run ad-hoc SQL |
| Data Steward | DS | Govern catalog, classifications, glossary |
| Researcher | R | Notebook-driven exploration, ML |
| Platform Admin | PA | Operate the platform, RBAC, infra |
| **Claims Analyst** | CA | Review claim cases (replaces WIA-beoordelaar) |
| **Operations Manager** | OM | Plan operational workflows (replaces SMZ-planner) |
| **Fraud Analyst** | FA | Detect anomalies, investigate (replaces WW-handhaver — keeps the "sensitive-data access" demo pattern) |
| **Marketing Analyst** | MA | Customer 360, segmentation (replaces CRM-medewerker + Proactief dienstverlener) |

### 4.3 Mock Keycloak users

```
data.engineer@odap.local
data.analyst@odap.local
data.steward@odap.local
researcher@odap.local
platform.admin@odap.local
claims.analyst@odap.local
operations.manager@odap.local
fraud.analyst@odap.local
marketing.analyst@odap.local
```

---

## 5. Demo data re-theming

### 5.1 Domain map

| UWV domain | New generic domain |
|---|---|
| WW (unemployment benefits) | `service_requests` |
| WIA (incapacity benefits) | `claims` |
| Wajong (youth disability) | `eligibility_cases` |
| ZW (sick leave) | `incident_reports` |
| Klantcontact / klanttevredenheid | `customer_interactions` / `customer_satisfaction` |
| CRM | `customers` (keep) |
| FEZ (finance/expense) | `financial_operations` |
| BSN (national ID) | `customer_id` |
| Doelbinding | "purpose limitation" (English label, same semantics) |

### 5.2 Use cases (UC-XX numbering kept)

| Old UC | New UC |
|---|---|
| UC-01 — Klant 360 (FEZ + WW) | UC-01 — **Customer 360** (transactions + interactions) |
| UC-05 — Client 360 lakehouse | UC-05 — **Customer Lifetime Value** |
| UC-11 — Klantreis | UC-11 — **Customer Journey** |
| (other UCs renamed similarly — final list to be confirmed when touching the files) | |

### 5.3 dbt model tree

```
dbt/models/staging/
  customers/       (was crm/)
  orders/          (new — replaces some of klantcontact)
  events/          (new — generic event-stream)
  claims/          (was wia/)
  service_requests/ (was ww/)
  incidents/       (was zw/)
  customer_satisfaction/ (was klantcontact/)
  finance/         (was fez/)
```

---

## 6. Compliance framework re-mapping

| Old (NL/EU) | New (international) | Notes |
|---|---|---|
| NORA | **SOC 2 Type II** | NORA is a NL government architecture framework — SOC 2 is its closest commercial peer. |
| AVG | **GDPR** | AVG is the Dutch implementation of GDPR; same regulation. |
| BIO / BIO2 | **ISO 27001 / 27002** | BIO is the Dutch baseline for government infosec; ISO 27001/2 is its international parent. |
| NIS2 | **NIS2** | EU-wide, keep. |
| AI Act | **EU AI Act** | EU-wide, keep. |
| Doelbinding | **Purpose limitation (GDPR Art. 5(1)(b))** | Direct GDPR term. |

Compliance docs (`docs/compliance-mapping.md`, the two root-level Dutch docs) get rewritten with this mapping. Where existing policies reference NORA principles, swap in SOC 2 trust-service-criteria language; where they reference BIO controls, cite the equivalent ISO 27002 control.

---

## 7. Execution phases (sequencing matters)

**Order is chosen so that each phase only depends on prior phases, and so that automated verification (helm template, kustomize build, mkdocs build) can run after each phase to catch breakage early.**

### Phase 1 — Branch + plan ✅ (in progress)
- Branch created: `feat/generic-rebrand-odap`
- This `PLAN.md` written and reviewed.

### Phase 2 — Infrastructure identifier rename (high blast radius, do first)
1. Namespaces: `uwv-{platform,data,meta,monitoring,auth}` → `odap-*` across all manifests, Helm values, scripts.
2. Hostnames: `*.uwv-platform.local` → `*.odap.local`; `freshstackable.com` / `eu-sovereigndataplatform.com` → `example.com`; emails `@uwv.nl`/`@uwv-platform.local` → `@example.com`/`@odap.local`.
3. Docker image registry prefix: `uwv-platform/*` → `odap/*`.
4. K8s label prefix: `uwv.nl/*` → `odap.io/*`.
5. Cert issuer name: `uwv-platform-issuer` → `platform-issuer`.
6. Trino cluster name + selector: `uwv-trino` → `trino`.
7. Postgres user: `uwvplatform` → `odap` (in dev secrets + initdb scripts + connection URIs).
8. S3 bucket names: drop `uwv-` prefix.
9. Keycloak realm: `uwv` → `odap`.
10. Env vars: `UWV_*` → drop prefix.
11. Python package: `uwv_lab` → `odap_lab`.
12. **Verify:** `kustomize build platform-overlays/k3d` succeeds; `helm template` succeeds for each chart; `grep -ri "uwv" platform/ infrastructure/ scripts/ | wc -l` drops to ~0.

### Phase 3 — File renames (git mv)
1. `git mv` for the 15 files in §3.9.
2. Update references to the moved files (e.g. `kubectl apply -f .../realm-uwv.json` → `realm.json`).
3. **Verify:** `git grep "realm-uwv\|trino-uwv-roles\|classifications-uwv\|pdb-uwv\|prometheusrule-uwv\|ensure_uwv_schemas\|uwv_role_mappings\|uwv-data-platform.svg"` returns 0 hits.

### Phase 4 — Portal UI translation + branding
1. Replace Dutch strings in `portal/src/layouts/ShellLayout.astro` (16 NL strings), `WorkspaceHome.astro` (8 strings), `CommandPalette.tsx`, `external-links.ts`.
2. Update `portal/package.json` description (NL → EN).
3. Update `portal/astro.config.mjs` site URL.
4. Update `portal/src/data/v2-homepage.ts` tile subtitles (currently mixed NL/EN).
5. Update `portal/src/data/components.ts` — translate `short` and `purpose` fields (~30 entries).
6. Rewrite logo SVG `uwv-data-platform.svg` → `odap-logo.svg` (new title + descriptive text, simple geometric mark; keep amber theme).
7. Update `mkdocs.yml` site_name, site_description, site_author, theme logo path.
8. Update `<title>` template in `ShellLayout` → "ODAP Portal".
9. **Verify:** `cd portal && npm run build` succeeds; visual check: no Dutch strings in built site.

### Phase 5 — Persona redesign
1. Rewrite persona table in `portal/src/layouts/ShellLayout.astro:69–75` and `WorkspaceHome.astro:125–140` to 9-persona set (§4.2).
2. Rewrite `infrastructure/helm/keycloak/realm.json` users + groups + role mappings.
3. Rewrite `opa-policies-src/data/role_mappings.json` to map new persona names.
4. Update dbt meta annotations referencing personas.
5. Update `portal/src/content/handleidingen/` → rename to `handbooks/`, prune to 9 (1 per persona) — see Phase 7 for content.
6. **Verify:** `opa test opa-policies-src/` passes; portal renders without missing persona icons.

### Phase 6 — Demo data re-theming
1. Rename dbt model folders per §5.3 (`crm/` → `customers/`, `wia/` → `claims/`, etc.).
2. Update dbt `_sources.yml`, `_stg_*.yml`, model SQL — column names: `bsn` → `customer_id`, `uitkeringsbedrag` → `claim_amount`, etc.
3. Update Spark jobs in `spark-jobs/` and `platform/08-spark/scripts/` to reference new schemas.
4. Update NiFi flow definitions in `nifi-flows/` (rename process groups + properties).
5. Update Airflow DAGs in `platform/11-airflow/dags/` (DAG IDs, task names, connection IDs).
6. Update synthetic data generators in `data-generation/` — generate customer/order/event/claim records instead of WIA/WW records.
7. Update OPA test fixtures (`opa-policies-src/**/*_test.rego`) with new persona + domain names.
8. Update Kafka topic names: `uwv.<domain>.<event>` → `<domain>.<event>`.
9. **Verify:** `dbt parse` succeeds; `dbt run --select state:modified+` works against a synthetic test target; `opa test opa-policies-src/` still green.

### Phase 7 — Documentation translation (largest phase)
1. **Root-level NL files (923 lines):**
   - `referentiearchitectuur-uwv-data-analytics.md` (734 lines, 100% Dutch) → rewrite as `reference-architecture.md` in English with new compliance mapping.
   - `requirements-compliant-data-analyseplatform.md` (189 lines, 100% Dutch) → rewrite as `requirements.md` in English.
2. **Role handbooks (`docs/handleidingen/` → `docs/handbooks/`, 12 files ~3000 lines):**
   - Condense from 12 → 9 (matching new persona set).
   - Each handbook: rewrite in English, generic scenarios (claims/orders/events instead of WIA/WW), keep structure (intro, tasks, data access, FAQ).
3. **Runbook + roadmap:**
   - `docs/runbook.md` (~80% Dutch) → full English.
   - `docs/improvements.md` (~70% Dutch) → full English; refresh roadmap items where they reference UWV-specific scenarios.
4. **Compliance docs:**
   - `docs/compliance-mapping.md` → re-mapped to SOC 2 / GDPR / ISO 27001 / NIS2 / AI Act.
5. **dbt schema descriptions:**
   - All `_*.yml` files in `dbt/models/` — translate Dutch column/table descriptions.
6. **Inline comments:**
   - Shell scripts in `scripts/` (~6 files with Dutch comments).
   - OPA policies in `opa-policies-src/` (Dutch policy comments).
   - Portal components (Dutch developer comments).
7. **READMEs:**
   - Root `README.md` (~30% Dutch) → full English with new platform pitch.
   - `portal/README.md`, `dbt/README.md`, `docs/README.md`, `platform/README.md`.
8. **Verify:** `mkdocs build --strict` passes; `find . -name '*.md' | xargs grep -lE '\b(voor|het|een|deze|naar|gebruiker|werkmap|doelbinding|tegel|aanvragen|uitloggen|werkplek)\b'` returns 0 results (with allowlist for code identifiers).

### Phase 8 — Verification & cleanup
1. **Final grep sweep:**
   - `git grep -i "uwv"` → 0 hits (except in `CHANGELOG.md` describing the rebrand).
   - `git grep "freshstackable.com\|eu-sovereigndataplatform.com\|uwv.nl"` → 0 hits.
   - Dutch-keyword sweep (`voor het een deze naar gebruiker werkmap doelbinding tegel`) → 0 hits in source.
2. **Build verification:**
   - `mkdocs build --strict`.
   - `kustomize build platform-overlays/k3d/` and `platform-overlays/aks/` succeed.
   - `helm template` for every chart in `infrastructure/helm/`.
   - `shellcheck scripts/**/*.sh`.
3. **Render verification:**
   - `cd portal && npm run build` — no errors, no NL strings.
4. **Cleanup:**
   - Update `WORKLOG.md` with rebrand entry.
   - Update `README.md` hero with new platform name + 1-paragraph pitch.
   - Update memory: amend `project_overview.md` to reflect ODAP naming + new domain.
5. **Commit & PR:**
   - Squash-or-stack commits per phase (better for review than one giant commit).
   - Optionally open PR with summary table of changes per phase.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Existing cluster runs on old namespaces.** Mass rename will break in-flight workloads. | This rebrand is for **fresh deploys**. The currently-running cluster keeps working on old names until torn down and redeployed against the new manifests. Document this clearly in WORKLOG.md. |
| **Mass find/replace hits unintended substrings.** e.g. `uwv` inside a base64-encoded secret. | Each rename pass uses precise patterns (word boundaries, file-type filters). After each pass: `git diff --stat` review + spot-check on randomly sampled files. |
| **Renaming a Trino catalog or DB user requires data-side migration.** | Documented but no live data exists here (synthetic only). Fresh deploy reseeds. |
| **OPA policies have logic + Dutch comments + Dutch test data interlocked.** Wrong rename = silent policy regression. | Run `opa test` after every rego rename. Tests already cover the relevant access patterns. |
| **Translation accuracy of legal/welfare terms.** | We're rewriting, not translating word-for-word. Generic scenarios sidestep most of the legalese. Compliance terms use the international-equivalent glossary in §6. |
| **Compiled portal bundle still has NL strings.** | Astro is SSG — all strings live in `.astro`/`.ts` sources. No precompiled bundles. |
| **PR review burden — one mega-commit is unreviewable.** | Commit per phase (8 commits). Each phase is independently verifiable. |
| **Logo SVG redesign — taste call.** | I will produce a clean geometric mark with "ODAP" wordmark in amber (current theme color). If you don't like it, swap easily — it's one file. |

---

## 9. What stays unchanged

These do **not** need rebranding:

- Apache 2.0 license (`LICENSE`).
- All third-party software (Stackable, Trino, Spark, Airflow, Keycloak, etc.) — only our wrapping changes.
- ADR files under `docs/adr/` (already vendor-neutral; only the filename of ADR-0002 changes).
- The Stackable operator naming (e.g. `airflowclusters.airflow.stackable.tech`) — those are upstream CRDs.
- `freshstackable-contact.json` (file name is already neutral; check contents).
- Deployment-mode architecture (k3d / aks split, kustomize overlays) — orthogonal to branding.
- Memory entries under `~/.claude/projects/.../memory/` — I'll update these as a final cleanup step so future sessions don't reference UWV.

---

## 10. Estimated effort

| Phase | Effort | Risk |
|---|---|---|
| Phase 1 (plan) | ~0.5 hr (done) | low |
| Phase 2 (infra rename) | ~2 hr | medium (blast radius) |
| Phase 3 (file renames) | ~0.5 hr | low |
| Phase 4 (portal UI) | ~2 hr | low |
| Phase 5 (personas) | ~1 hr | medium (OPA test fixtures interlock) |
| Phase 6 (demo data re-theme) | ~3 hr | medium |
| Phase 7 (docs translation) | ~6 hr | low (most repetitive) |
| Phase 8 (verification) | ~1 hr | low |
| **Total** | **~16 hr** of focused work | — |

Numbers are rough — they reflect agent-paced effort, not the original ~160-240 human-hour estimate the audit produced. Real wall time depends on cluster of tool calls, not human keystrokes.

---

## 11. How execution will look

Per phase:
1. Update the corresponding task in TaskList to `in_progress`.
2. Apply changes via `Edit`/`Write`/`git mv` — many parallel tool calls where independent.
3. Run the phase's "Verify" step.
4. Commit the phase with a clear message.
5. Mark task `completed`, move to next phase.

If anything looks off mid-phase (e.g. a verify step fails for non-obvious reasons), I stop and check in before pressing on.

---

**Awaiting your approval to proceed with Phase 2.** If anything in this plan needs adjustment — the persona set, the use-case renames, the compliance mapping, the new namespace names — flag it now; fixing the dictionary is far cheaper than reversing renames after the fact.
