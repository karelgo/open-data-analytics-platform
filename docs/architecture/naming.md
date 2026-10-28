# Naming conventions

The same job-market subject crosses every layer.

| Name | Meaning |
|---|---|
| `bronze.job_market.observations` | Source observations partitioned by snapshot date |
| `silver.job_market.stg_job_observations` | Standardized analytical records |
| `silver.job_market.int_job_snapshots` | Deduplicated group/day records |
| `gold.job_market.mart_job_inventory` | Inventory in the latest observed snapshot |
| `gold.job_market.mart_job_demand_daily` | Daily demand by overlapping domain |
| `gold.job_market.mart_job_skills` | Skill demand |
| `gold.job_market.mart_job_salary` | Salary evidence with original units and estimate flags |
| `gold.job_market.mart_job_geography` | Geography |
| `gold.job_market.mart_job_work_arrangements` | Contracts and work arrangements |
| `gold.job_market.mart_job_source_quality` | Source-level completeness and provenance |
| `dutch_it_jobs_daily` | Airflow DAG |
| `dutch-it-job-market` | Superset dashboard slug |
| `snapshot_date=YYYY-MM-DD/` | Dated extraction partition |

Domains use stable lowercase values: `data`, `cloud`, `sap`, `ai`, `software`, `security`. Unknown facts remain null or explicit unknown categories as documented; they must not be inferred from unrelated vacancies.
