# UC-12 — Cloud-cost FinOps (FOCUS)

**Doel**: maandelijkse cloud-billing-export (FOCUS-formaat) van OCI/AWS/Azure/GCP omzetten in een end-to-end FinOps-dashboard met spend-trends, service-breakdowns, commitment-utilization en top-resource-analyse.

**Volgt het CSV-upload-patroon** dat customer_satisfaction (UC11-naburig) introduceerde. Geen Kafka, geen streaming — gebruiker uploadt een CSV via de portal en de pipeline draait automatisch tot Superset.

---

## 1. Verhaal

UWV draait workloads bij meerdere cloud-providers (primair OCI). Finance wil per maand zien:

1. **Hoeveel geven we uit, waar gaat het heen, en hoe verandert dat?**
2. **Hoeveel besparen we t.o.v. lijstprijzen, en gebruiken we onze committed-discounts optimaal?**
3. **Welke resources/applicaties veroorzaken de meeste spend?**

[FOCUS](https://focus.finops.org/) is de open FinOps-spec voor billing-data — eenduidige kolomnamen ongeacht provider. De OCI-export volgt FOCUS 1.x core (39 kolommen) + 10 `oci_*` vendor-extensies, samen 49 kolommen. UC-12 ondersteunt beide: de oci_*-kolommen mogen leeg zijn voor non-OCI uploads.

---

## 2. End-to-end flow

```
Finance medewerker
   │  Upload focus-yyyymm.csv via mc CLI of MinIO Console
   │  (portal /csv-upload is sinds 2026-05 generiek — zie handbooks/csv-upload.md Pad B)
   ▼
MinIO  s3://odap-staging/incoming/focus/<ts>-<file>.csv
   │  (handmatige trigger: Airflow UI of REST API)
   ▼
ingest_csv_focus DAG (auto-generated door csv_ingest_factory)
   │  csv_to_bronze.py — pyarrow type-cast + validatie tegen sources/focus.yml
   ▼
bronze.finops.focus_billing  (Delta, partitioned by event_date)
   │  Airflow Dataset trigger
   ▼
silver_finops DAG (Cosmos dbt run --select tag:finops,tag:staging)
   │  ↓
   ▼
silver.finops.stg_focus_billing  (view; snake_case + tags JSON-parse + billing_month)
   │  Airflow Dataset trigger
   ▼
gold_uc12_focus_finops DAG (Cosmos dbt run --select tag:uc12)
   │  ↓
   ▼
gold.uc12_focus_finops.mart_uc12_focus_*  (5 marts, Delta tables)
   │
   ▼
Superset dashboard "uc12-focus-finops"
```

---

## 3. Datamodel

### Bronze — `bronze.finops.focus_billing`

Native FOCUS-kolommen (PascalCase) + 3 audit-kolommen (`ingestion_ts`, `source_file`, `event_date`). Partitionering op `event_date` = upload-datum. Delta-formaat (Iceberg via `TABLE_FORMAT=iceberg`).

Schema-definitie: [platform/11-airflow/sources/focus.yml](../../platform/11-airflow/sources/focus.yml).

### Silver — `silver.finops.stg_focus_billing` (view)

- PascalCase → snake_case
- `provider` lowercased
- `tags` JSON geparsed → drie expliciete kolommen (`tag_environment`, `tag_application`, `tag_cost_center`)
- Afgeleide `billing_month` = `date_trunc('month', BillingPeriodStart)` — primaire grain voor alle marts
- Afgeleide `savings_amount` = `coalesce(list_cost, effective_cost) - effective_cost`

Model: [dbt/models/staging/finops/stg_focus_billing.sql](../../dbt/models/staging/finops/stg_focus_billing.sql).

### Gold — 5 marts in `gold.uc12_focus_finops`

| Mart | Grain | Bron-rol |
|---|---|---|
| `mart_uc12_focus_spend_monthly` | `billing_month × provider × service_category × charge_category` | KPI-strip + spend-trend |
| `mart_uc12_focus_service_breakdown` | `billing_month × service_name × region × environment × application` | Pie-charts + drill-down |
| `mart_uc12_focus_commitment_utilization` | `billing_month × provider × service_category` | Commitment-coverage % + savings % |
| `mart_uc12_focus_top_resources` | `billing_month × resource_id` (+ `rank_in_month`) | Top-50 resources tabel |
| `mart_uc12_focus_savings` | `billing_month × provider × pricing_category × service_category` | Savings-breakdown |

Models in [dbt/models/marts/uc12_focus_finops/](../../dbt/models/marts/uc12_focus_finops/).

---

## 4. Het dashboard

Slug: **`uc12-focus-finops`** — `https://superset.odap.local:8443/superset/dashboard/uc12-focus-finops/`.

Layout (5 rijen):

1. **KPI-strip** (4 × width 3): totale effective cost · totale list cost · totale savings · gem. commitment coverage
2. **Trends** (2 × width 6): effective cost per maand per provider · commitment coverage % per maand per service-categorie
3. **Breakdowns** (3 × width 4): pie's voor service-categorie · regio · environment
4. **Drill-downs** (2 × width 6): top-10 services · spend per applicatie (uit tags)
5. **Detail-tabel** (1 × width 12): top-50 resources op spend deze maand

Config: [platform/12-superset/dashboards-init-job.yaml](../../platform/12-superset/dashboards-init-job.yaml).

---

## 5. Hoe upload je een nieuwe maand

### Voorwaarden

- Keycloak-account heeft user-attribute `policy: csv-uploader` (de `csv-uploader`
  MinIO-policy dekt zowel `uploads/*` als legacy `incoming/*`; zie
  [infrastructure/helm/minio/values.yaml](../../infrastructure/helm/minio/values.yaml)).
- CSV-header **moet exact** de 50 kolomnamen uit [sources/focus.yml](../../platform/11-airflow/sources/focus.yml) bevatten — `csv_to_bronze.py` faalt anders met `ERROR: CSV mist kolommen: [...]`.
- Timestamps in ISO 8601 (`2026-05-01T00:00:00Z` of `2026-05-01T00:00:00.000Z`).
- `BillingCurrency` is per upload homogeen verondersteld (MVP); meertonen-uploads splits je apart.

### Stappen

Sinds 2026-05 is de portal-uploader generiek — hij schrijft naar `uploads/`,
niet `incoming/`. Voor FOCUS gebruik je daarom de mc CLI en trigger je daarna
de DAG handmatig:

```bash
# 1. Upload het bestand
mc alias set minio https://minio.odap.local:8443 platformadmin \
  'odap-dev-only-CHANGE-ME' --insecure
TS=$(date -u +%Y%m%dT%H%M%S)
mc cp ./focus-2026-05.csv \
  minio/odap-staging/incoming/focus/${TS}.csv --insecure

# 2. Trigger de ingest-DAG via Airflow REST
curl -fsS -u "airflow:odap-dev-only-CHANGE-ME" \
  -X POST -H 'Content-Type: application/json' \
  -d "{\"conf\":{\"object_key\":\"incoming/focus/${TS}.csv\"}}" \
  https://airflow.odap.local:8443/api/v1/dags/ingest_csv_focus/dagRuns
```

Of via de Airflow UI: open `ingest_csv_focus`, klik **Trigger DAG w/ config**
en geef `{"object_key": "incoming/focus/<ts>.csv"}`.

1. Bekijk progress in Airflow: https://airflow.odap.local:8443/dags/ingest_csv_focus.
2. Bij succes ververst het Superset-dashboard zodra `gold_uc12_focus_finops` klaar is (5-15 min na upload, afhankelijk van rij-aantal).

### Test-CSV genereren

```bash
python3 scripts/finops-generate-focus-csv.py --output /tmp/focus-test.csv
# ~550 rijen, 3 maanden × 4 compartments × 8 services × 4 regio's
```

Aanpassingen via flags: `--months 6 --seed 99 --end-year 2026 --end-month 4`.

---

## 6. Bestandsindex

**Source-registry**
- [platform/11-airflow/sources/focus.yml](../../platform/11-airflow/sources/focus.yml) — 50-kolom FOCUS-schema, bronze/silver/governance specs

**Ingest**
- [platform/11-airflow/jobs/csv_to_bronze.py](../../platform/11-airflow/jobs/csv_to_bronze.py) — bevat de `decimal`/`timestamp` ondersteuning die FOCUS nodig heeft

**dbt — staging**
- [dbt/models/staging/finops/stg_focus_billing.sql](../../dbt/models/staging/finops/stg_focus_billing.sql)
- [dbt/models/staging/finops/_stg_focus_billing.yml](../../dbt/models/staging/finops/_stg_focus_billing.yml)
- [dbt/models/staging/_sources.yml](../../dbt/models/staging/_sources.yml) — `focus_billing`-tabel-entry onder `bronze`-source

**dbt — marts**
- [dbt/models/marts/uc12_focus_finops/mart_uc12_focus_spend_monthly.sql](../../dbt/models/marts/uc12_focus_finops/mart_uc12_focus_spend_monthly.sql)
- [dbt/models/marts/uc12_focus_finops/mart_uc12_focus_service_breakdown.sql](../../dbt/models/marts/uc12_focus_finops/mart_uc12_focus_service_breakdown.sql)
- [dbt/models/marts/uc12_focus_finops/mart_uc12_focus_commitment_utilization.sql](../../dbt/models/marts/uc12_focus_finops/mart_uc12_focus_commitment_utilization.sql)
- [dbt/models/marts/uc12_focus_finops/mart_uc12_focus_top_resources.sql](../../dbt/models/marts/uc12_focus_finops/mart_uc12_focus_top_resources.sql)
- [dbt/models/marts/uc12_focus_finops/mart_uc12_focus_savings.sql](../../dbt/models/marts/uc12_focus_finops/mart_uc12_focus_savings.sql)
- [dbt/models/marts/uc12_focus_finops/_uc12.yml](../../dbt/models/marts/uc12_focus_finops/_uc12.yml)

**dbt — config**
- [dbt/dbt_project.yml](../../dbt/dbt_project.yml) — `finops` staging-schema + `uc12_focus_finops` mart-schema
- [dbt/macros/ensure_schemas.sql](../../dbt/macros/ensure_schemas.sql) — bootstrap silver.finops + gold.uc12_focus_finops met S3-locatie

**Superset**
- [platform/12-superset/dashboards-init-job.yaml](../../platform/12-superset/dashboards-init-job.yaml) — `uc12-focus-finops`-blok met 5 charts × 5 datasources

**Tools**
- [scripts/finops-generate-focus-csv.py](../../scripts/finops-generate-focus-csv.py) — synthetic FOCUS-CSV generator

---

## 7. Bekende beperkingen (MVP)

| Beperking | Impact | Roadmap |
|---|---|---|
| Geen multi-currency normalisatie | Heterogene uploads tellen euro's + dollars op | FX-rate lookup macro in silver |
| Geen commitment-amortisatie | Upfront-fees verschijnen alleen in maand van betaling | `int_focus_amortized.sql` (fase 2) |
| Tags-parser leest alleen JSON | OCI levert standaard JSON; AWS/Azure key=value-format faalt stil → `tag_*` = NULL | Heuristic in silver detecteren en parsen |
| Geen budget-alerting | Spend-spike triggert geen alert | Vector log-alert op `mart_uc12_focus_spend_monthly` MoM-delta > threshold |
| Handmatige upload | Geen scheduled OCI-API pull | `ingest.kind: oci_api` source-mode + Airflow daily-pull |
| Geen RLS op finance-dashboard | Iedereen met dashboard-rechten ziet alles | Keycloak `finops`-rol + Superset role-mapping op `uc12-focus-finops` |

---

## 8. Verder lezen

- [FOCUS Specification 1.x](https://focus.finops.org/) — kolom-semantiek, accepted values, vendor-extensies
- [docs/use-cases/uc11-customer-journey-walkthrough.md](uc11-customer-journey-walkthrough.md) — platform-rondleiding (zelfde patroon, ander domein)
- [platform/11-airflow/include/csv_ingest_factory.py](../../platform/11-airflow/include/csv_ingest_factory.py) — hoe `ingest_csv_focus` DAG automatisch wordt gegenereerd
