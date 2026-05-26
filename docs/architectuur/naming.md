---
title: Naming conventions
description: Namen voor namespaces, schemas, topics, DNS — consistent over alle componenten.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Wijzigingen handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Naming conventions

Eén consistente naamgevingsstrategie maakt zoeken in OpenMetadata, lineage
en logs een stuk eenvoudiger. Alle componenten houden zich hieraan.

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
| `bronze.uwv.<entity>` | `bronze.uwv.wia_aanvraag`, `bronze.uwv.ww_uitkering` |
| `silver.<domain>.<entity>` | `silver.wia.aanvraag_pseudo`, `silver.crm.contact` |
| `gold.<uc_id>.<artifact>` | `gold.uc01_wia_funnel.daily_kpi`, `gold.uc05_client_360.profile` |
| `sensitive.<domain>.<entity>` | `sensitive.medisch.diagnose` |

Domein-codes: `ww`, `wia`, `wajong`, `crm`, `fez`, `polisadm`, `smz`.

## dbt-modellen

```
<layer>_<domain>_<entity>.sql
```

Voorbeelden:

- `stg_wia_aanvraag.sql` — staging-laag
- `int_wia_funnel_daily.sql` — intermediate
- `mart_uc01_wia_funnel_daily.sql` — mart (gold)

## Kafka-topics

```
uwv.<domain>.<event>
```

Voorbeelden:

- `uwv.wia.aanvraag`
- `uwv.wia.beoordeling`
- `uwv.ww.uitkering`

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
