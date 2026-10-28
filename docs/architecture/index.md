# Architecture: Dutch IT Job Market

One daily job-market pipeline connects the platform's data services. This page describes the active path; optional streaming and vendor integrations are outside the example.

```mermaid
flowchart TB
  API[Adzuna Netherlands / approved job feeds] --> AF[Airflow: dutch_it_jobs_daily]
  AF --> RAW[MinIO: dated raw responses and extraction manifest]
  AF --> SP[Spark: daily Bronze Delta observations]
  SP --> HMS[Hive Metastore]
  HMS --> TR[Trino: bronze.job_market.observations]
  TR --> DBT[dbt: Silver normalization and deduplication]
  DBT --> GOLD[Gold: inventory, demand, skills, salary, geography, work and quality]
  GOLD --> BI[Superset]
  GOLD --> NB[Jupyter]
  DBT --> OM[OpenMetadata: definitions, lineage and tests]
  KC[Keycloak] --> OPA[OPA: Trino authorization]
  OPA -. permissions .-> TR
  OBS[Prometheus / Grafana / OpenSearch] -. platform health .-> AF
```

| Layer | Active implementation |
|---|---|
| Sources | `examples/dutch-it-jobs/sources.json`; offline synthetic fixtures or explicitly selected live APIs/feeds |
| Raw evidence | Date-partitioned responses and extraction manifest; restricted storage |
| Bronze | `bronze.job_market.observations`, written idempotently by Spark into Delta |
| Silver | `silver.job_market.stg_job_observations` and `int_job_snapshots` |
| Gold | `gold.job_market.mart_job_*`, materialized and tested through dbt |
| Consumption | Superset dashboard, `/job-market/` sample explorer and Jupyter starter notebook |
| Governance | Keycloak authentication, OPA authorization, OpenMetadata catalog and dbt lineage |
| Operations | Airflow schedule at 05:00 Europe/Amsterdam; extraction manifests and service logs |

[Full walkthrough and data dictionary](../use-cases/dutch-it-job-market.md) · [Data zones](datazones.md) · [Naming](naming.md) · [Identity and authorization](auth.md).
