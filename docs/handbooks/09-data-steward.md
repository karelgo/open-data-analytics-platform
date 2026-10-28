# Data Steward

Own job definitions, source provenance, quality tests and classifications. All exercises use the same Dutch IT Job Market pipeline. The existing identity key `data_steward` remains for compatibility with Keycloak accounts; it does not activate an earlier business use case.

## Start

Open the portal's `/job-market/` page, then the Superset dashboard `dutch-it-job-market`. Sign in through Keycloak for platform services. Offline sample records are synthetic; live observations require explicitly configured source access.

Your analytical scope is **the job-market tables granted to your role**. Do not assume that access to a chart grants access to source payloads. Raw responses can contain contact details and remain restricted.

## Daily task

Own job definitions, source provenance, quality tests and classifications.

```sql
SELECT *
FROM gold.job_market.mart_job_inventory
LIMIT 20;
```

Inspect the same table in OpenMetadata and follow its dbt lineage to `silver.job_market.int_job_snapshots` and `bronze.job_market.observations`. Query underlying layers only when your role permits it.

## Interpretation checklist

- Compare the same snapshot dates and source coverage. A failed source can change counts.
- Domain labels overlap. A Cloud Security Engineer can belong to both domains.
- Separate reported from estimated pay. Monthly EUR amounts are annualized × 12; hourly pay remains a separate unit.
- Missing fields are unknown. A listing absent from a bounded search is not proven closed.
- Preserve `source`, `source_job_id`, `canonical_url`, `snapshot_date` and `is_synthetic` in evidence.

## When something fails

For stale data, inspect Airflow's `dutch_it_jobs_daily` and the dated extraction manifest. For denied access, verify the signed-in role and ask the asset owner through the access-request page. For definitions or source completeness, contact the data steward. Platform logs and service dashboards are available to approved operational roles.

[Complete walkthrough and data dictionary](../use-cases/dutch-it-job-market.md).
