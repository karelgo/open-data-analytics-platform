---
title: Naming conventions
description: Namen voor namespaces, schemas, topics, DNS — consistent over alle components.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Changes handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Naming conventions

Eén consistente naamgevingsstrategie maakt zoeken in OpenMetadata, lineage
en logs een stuk eenvoudiger. Alle components houden zich hieraan.

## Kubernetes namespaces

| Namespace | Inhoud |
|---|---|
| `odap-platform` | Stackable workloads (Trino, Spark, Kafka, NiFi, OPA, …) |
| `odap-data` | Synthetic data jobs, dbt-runners |
| `odap-meta` | OpenMetadata stack |
| `odap-monitoring` | Prometheus, Grafana, Vector |
| `odap-auth` | Keycloak |

## Trino-schemas

| Pattern | Voorbeelden |
|---|---|
| `bronze.demo.<entity>` | `bronze.claims.application`, `bronze.demo.ww_claim payout` |
| `silver.<domain>.<entity>` | `silver.claims.application_pseudo`, `silver.customers.interaction` |
| `gold.<uc_id>.<artifact>` | `gold.uc01_claims_funnel.daily_kpi`, `gold.uc05_customer_360.profile` |
| `sensitive.<domain>.<entity>` | `sensitive.medisch.diagnose` |

Domein-codes: `ww`, `wia`, `wajong`, `crm`, `fez`, `polisadm`, `smz`.

## dbt-models

```
<layer>_<domain>_<entity>.sql
```

Voorbeelden:

- `stg_claim_application.sql` — staging-laag
- `int_wia_funnel_daily.sql` — intermediate
- `mart_uc01_claims_funnel_daily.sql` — mart (gold)

## Kafka-topics

```
uwv.<domain>.<event>
```

Voorbeelden:

- `claims.application`
- `<domain>.wia.beoordeling`
- `<domain>.ww.claim payout`

## DNS

```
<service>.odap.local
```

Voor lokale k3d-clusters. In AKS-deploys (`example.com`)
rewrite de portal client-side; zie
[`portal/src/layouts/Layout.astro`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/portal/src/layouts/Layout.astro).

## OpenMetadata services

| Service-naam | Inhoud |
|---|---|
| `trino-prod` | Trino-instance met alle catalogs (bronze/silver/gold/sensitive/sandbox) |
| `dbt` | dbt-project (lineage + tests) |
| `superset-prod` | Superset BI (dashboards) |
| `airflow` | Airflow (pipeline-runs) |
| `kafka` | Kafka (event-topics + schemas) |
