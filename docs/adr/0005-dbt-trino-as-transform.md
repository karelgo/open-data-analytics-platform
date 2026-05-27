# ADR-0005: dbt-core + dbt-trino als transformationlaag

| Status | **Geaccepteerd** |
|---|---|
| Datum | 2026-04-30 |
| Beslissers | Platform Architect, Data Office, Lead Data Engineer |
| Gerelateerd | ADR-0001 (Stackable), ADR-0002 (table format), ADR-0004 (OpenMetadata) |

---

## Context

We hebben een transformationlaag nodig tussen bronze (raw, incl. PII) en
silver/gold (CGM-conform, business-ready). Eisen:

- SQL-first: domein-experts en analisten schrijven SQL, geen JVM-builds.
- Versionable + reviewable per PR.
- Tests in pipeline (uniqueness, not-null, accepted values, custom business rules).
- Documentation genereerbaar (lineage, descriptions).
- Compatibel met Trino + Iceberg/Delta.
- CGM-naming en purpose-limitation-tags afdwingbaar.
- Open source, Apache 2.0.

---

## Beslissing

**dbt-core + dbt-trino adapter** is de transformationlaag, draaiend in
**Airflow K8s-pods** (KubernetesPodOperator).

---

## Motivatie

- **dbt-trino is officieel** (Starburst + community), Apache 2.0, naadloze
  Iceberg- én Delta-ondersteuning via `properties{}` in `config()`.
- **Macros zijn de juiste tool voor format-abstractie** (zie ADR-0002 §
  Implementatie-impact). Eén macro `table_format_properties()` switcht
  Iceberg ↔ Delta.
- **Built-in tests + dbt-utils + dbt-expectations** dekken UWV-business-rules
  (BSN-checksum, IBAN-format, accepted-values voor wet/claim payoutssoort).
- **`manifest.json` + `catalog.json` + `run_results.json`** zijn de input voor
  OpenMetadata's dbt-workflow → automatische lineage en descriptions in OM.
- **`meta` op model-niveau** (legal_basis, purpose-limitation, retention period,
  pii_kolommen, risk_tier) is een natuurlijke plek voor compliance-metadata
  die OM via tags overneemt.
- **Snapshots** voor SCD-tracking (bv. dossier-status-historie).
- **Geen separate runtime**: dbt-runs draaien als Airflow-pods → één
  orchestratie-laag (R-NF-03).

---

## Risico's en mitigaties

| Risico | Mitigatie |
|---|---|
| dbt-trino kent minder materializations dan dbt-snowflake/redshift | Voor platform workloads (table, view, incremental, materialized_view) is dekking voldoende |
| Materialized Views in Trino voor Delta zijn beperkt (ADR-0002) | Default `materialized='table'`; MV alleen waar zinvol en op Iceberg-modus |
| `target/` directory met manifests kan groot worden | Niet committen; `dbt-artifacts.zip` upload naar `s3://odap-meta/dbt/` per run |
| `profiles.yml` bevat credentials | Niet committen; renderen vanuit Kubernetes Secret in Airflow-pod |

---

## Niet gekozen alternatieven

- **SQLMesh**. Veelbelovend, met betere virtual-environments, maar minder
  rijp dan dbt; kleinere community; minder OpenMetadata-integratie. Te jong
  voor reference implementation.
- **Apache Spark SQL + custom orchestratie**. Geen tests-by-default, geen
  manifest, geen catalog-integratie. Skip.
- **Hand-geschreven SQL via Airflow SQLOperator**. Geen tests, geen
  documentation, geen lineage. Skip.

---

## Implementatie-impact

- `dbt/dbt_project.yml` — top-level project met `vars: table_format`.
- `dbt/profiles.yml.template` — Trino-profile met OIDC-auth tegen Keycloak.
- `dbt/macros/table_format.sql` — formaat-abstractie macro.
- `dbt/macros/pseudonymize.sql` — hash + zout helper.
- `dbt/macros/apply_purpose-limitation_tag.sql` — schrijft `meta` naar dbt-docs +
  OM-pickup.
- `dbt/models/{staging,intermediate,marts/uc0x_*}` — models per laag/UC.
- `dbt/tests/` — singular tests; per-model tests via `schema.yml`.
- Airflow DAG `dbt_run_per_domain.py` — KubernetesPodOperator met dbt-image.
- CI: `dbt parse` + `dbt compile` + `dbt-checkpoint` (best-effort).
