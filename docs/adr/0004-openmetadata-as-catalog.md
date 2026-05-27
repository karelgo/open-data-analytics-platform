# ADR-0004: OpenMetadata als catalog, governance en lineage-laag

| Status | **Geaccepteerd** |
|---|---|
| Datum | 2026-04-30 |
| Beslissers | Platform Architect, Data Office |
| Gerelateerd | ADR-0001 (Stackable), ADR-0003 (OPA), ADR-0005 (dbt-trino) |

---

## Context

compliance vereist een data catalog met:

- Technische én business-metadata per data product (R-GOV-02).
- End-to-end **data lineage** op tabel- én kolomniveau (R-GOV-03).
- **Classifications**: PII, BIO-classificatie, gezondheid art. 9 AVG,
  purpose-limitation-doelen, AI-risk-tier.
- Verplicht koppelen aan **CGM** (Canoniek Gegevensmodel) via een glossary
  met business-terms.
- Profiler + data-quality-tests met SLA's (R-GOV-04, UC-07).
- Auto-classification (PII-detectie, BSN-patronen) bij ingestion.
- API-access voor automatisering (R-NORA-02).

Drie open source kandidaten: **DataHub**, **Apache Atlas**, **OpenMetadata**.

---

## Beslissing

**OpenMetadata 1.12+** is de catalog/governance/lineage/DQ-laag.

---

## Motivatie

- **Eén tool, vier capabilities**. OpenMetadata combineert catalog, lineage,
  classifications én DQ-profiler. Bij DataHub zit DQ in een aparte tool;
  Atlas heeft geen native profiler. Voor UWV scheelt dit één integratie-punt.
- **Sterke dbt-integratie**. OpenMetadata leest dbt's `manifest.json`,
  `catalog.json` en `run_results.json` direct → kolomniveau-lineage komt
  "gratis" mee from the SQL.
- **Trino-connector volwassen**. Schema-discovery, query-history-lineage,
  profiler en DQ-tests werken out-of-the-box.
- **Glossary + Domains + Data Products**. Past 1-op-1 op UWV's mesh-model
  (WW/AG/CRM/FEZ als Domains, gold-tabellen als Data Products).
- **REST API + Python SDK**. Tags, owners, descriptions zijn programmatisch
  pushbaar — past bij "policy-/governance-as-code".
- **Helm-chart van vendor**. `openmetadata-helm-charts` is de officiële chart;
  geen zelfgebouwde manifests nodig.
- **Reverse Metadata** (sinds 1.7+) maakt het mogelijk om tags vanuit OM
  terug naar Trino te schrijven → mogelijk pad naar OPA-policy-feed.

---

## Risico's en mitigaties

| Risico | Mitigatie |
|---|---|
| OpenMetadata zelf is een groot stack (Java + MySQL/Postgres + OpenSearch + Airflow-of-eigen orchestrator) | Gebruik scaled-down profiel; deel OpenSearch met Vector logs; deel Postgres met Airflow/Superset |
| Versie-vrijheid: vendor pusht features achter "Collate" (commercial) | We blijven op community edition; Reverse Metadata (community sinds #25970) is voldoende |
| Auto-classification kan false-positives op BSN-patronen geven | Lijst handmatig reviewen; bevestiging in OM UI vereist voordat tag actief wordt |
| Lineage-workflow vereist query-history | Trino-event-listener naar Kafka schrijft query log; OM leest het |

---

## Niet gekozen alternatieven

- **DataHub**. Sterke catalog en lineage, maar DQ vereist apart Great Expectations of Soda; classifications minder rijk; UI en navigatie zwaarder. Skip — meer integratie-werk.
- **Apache Atlas**. Atlas is solide voor Hadoop-ecosystemen, maar de Trino-integratie en dbt-integratie zijn beperkt; community-momentum is laag. Skip.
- **Microsoft Purview / Collibra / Alation**. Proprietary; conflict met R-NORA-04 (open standaarden). Skip.

---

## Implementatie-impact

- `infrastructure/helm/openmetadata/values.yaml` — chart-config (scaled-down,
  shared OpenSearch + Postgres).
- `platform/13-openmetadata-config/` — declaratieve service- en
  ingestion-pipeline-definities (gepusht via OM REST API through the in-cluster
  Job in [`init-job.yaml`](../../platform/13-openmetadata-config/init-job.yaml);
  glossary-link + dbt-meta enrichment-jobs draaien als CronJob).
- `dbt/dbt_project.yml` — exporteer `manifest.json` etc. naar
  `s3://odap-meta/dbt/<run_id>/`.
- Trino — event-listener config naar Kafka topic `uwv.trino.queries` voor
  lineage capture.
- Airflow DAGs `om_ingest_*` halen periodiek metadata op.
