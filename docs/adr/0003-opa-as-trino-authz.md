# ADR-0003: Open Policy Agent als authorisatielaag voor Trino

| Status | **Geaccepteerd** |
|---|---|
| Datum | 2026-04-30 |
| Beslissers | Platform Architect, CISO, Data Office |
| Gerelateerd | ADR-0001 (Stackable), ADR-0004 (OpenMetadata) |

---

## Context

Trino moet rijke authorisatie afdwingen die past bij UWV's compliance-eisen:

- **Doelbinding** (R-AVG-06): toegang tot een dataset is gekoppeld aan een doel
  (uitkering, re-integratie, handhaving, statistiek). Een query die niet
  matcht met de doelcode van de gebruiker wordt geweigerd.
- **Dataminimalisatie** (R-AVG-05): kolommen worden alleen blootgesteld als de
  rol/het doel daar aanleiding toe heeft.
- **Column-level security & masking** (R-BIO-11): BSN, IBAN, diagnose,
  bankrekening worden gemaskeerd voor rollen die ze niet primair nodig
  hebben (bv. `marketing_analyst` ziet `'XXXXX' || substring(bsn, 6)` ipv ruwe BSN).
- **Row-level security** (R-BIO-11): Claims Analysts zien alleen dossiers in
  hun regio; Finance Analysten zien geen individu-rijen.
- **Audit-log van decisies** (R-BIO-20): elke deny is herleidbaar.

Trino ondersteunt drie plug-bare authorizers: `file`, `system-property` en
**OPA**. Sinds Trino 438 ondersteunt de OPA-authorizer batched evaluation,
column masking en row filtering rechtstreeks vanuit Rego.

---

## Beslissing

**Open Policy Agent (Rego) is de authorisatielaag voor Trino**, gedeployed
als `OpaCluster` (Stackable) en geconfigureerd via een ConfigMap-bundle.

---

## Motivatie

- **Policy-as-code** (R-GOV-06): Rego is testbaar (`opa test`), versionable en
  reviewable in PR's. Tegenover hard-coded ACL's of database-grants is dit een
  significante audit-winst.
- **Eén taal voor alle policy-typen**: doelbinding, RBAC, ABAC, column masks
  en row filters zitten in één Rego-bundle. Geen versnipperde mechanismen.
- **Stackable-native integratie**: OpaCluster + ConfigMap met label
  `opa.stackable.tech/bundle: "true"` wordt automatisch ingelezen door OPA
  en hot-reloaded zonder Trino-restart.
- **OpenMetadata-integratie pad**: tags die in OM op kolommen staan
  (bijvoorbeeld `Doelbinding.uitkering`) kunnen via reverse-metadata of een
  custom export naar de OPA-data feed → policies blijven dichtbij de catalog.
- **Open source en vendor-neutraal**: CNCF-graduated project (sinds 2021);
  geen lock-in.

---

## Risico's en mitigaties

| Risico | Mitigatie |
|---|---|
| Rego heeft een leercurve | Pair-programming + dedicated repo `opa-policies-src/` met tests; CI faalt bij geen tests |
| Performance bij hoge concurrency | Batched evaluation aan; OPA replica-count schalen; metrics monitoren |
| Decisie-logging volume | Log alleen denies + sample van allows; OpenSearch retention-tier |
| Policy bug = data-leak | `opa test` verplicht in CI; formele review per PR; default-deny op `sensitive` catalog |

---

## Niet gekozen alternatieven

- **Apache Ranger**. Krachtig maar zwaar (eigen UI, eigen DB, integratie via
  plugins). Niet pre-geconfigureerd in Stackable. Skip — past niet bij
  "lichte, code-driven policy"-doel.
- **Trino file-based access control**. Geen ABAC, geen column masking,
  geen row filters via expressies. Te beperkt voor doelbinding-eisen.
- **Database-grants (Trino-gebruikers per Hive-schema)**. Werkt voor
  catalog/schema-toegang, niet voor row/column-niveau. Skip.
- **Unity Catalog**. Databricks-specifiek; out of scope per ADR-0001.

---

## Implementatie-impact

- `platform/10-opa/opacluster.yaml` — Stackable OpaCluster (1 replica
  scaled-down).
- `platform/10-opa/policies/*.rego` — base, RBAC-rollen, doelbinding, row
  filters, column masks; `*_test.rego` voor unit tests.
- `opa-policies-src/` — bron van waarheid; `make build-opa-bundle` rendert
  naar ConfigMap.
- `platform/09-trino/trinocluster.yaml` — `accessControl.opa.url:
  http://opa.odap-platform.svc.cluster.local:8081` (intern endpoint).
- CI: `opa fmt --diff` + `opa test` zijn verplichte stappen.
