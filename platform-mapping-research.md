# Active implementation map

| Capability | Implementation |
|---|---|
| Daily extraction and local analytics | `examples/dutch-it-jobs/` |
| Raw and Bronze storage | `spark-jobs/job_market_bronze.py`, MinIO and Delta |
| Daily orchestration | `platform/11-airflow/dags/dutch_it_jobs_daily.py` |
| Silver/Gold models and tests | `dbt/` |
| Dashboard | `platform/12-superset/` |
| Governance and catalog | `opa-policies-src/`, `platform/13-openmetadata-config/` |
| Notebook | `platform/16-jupyter/starter-notebooks/00_dutch_it_job_market.ipynb` |
| Interactive sample explorer | `portal/src/pages/job-market.astro` |

See the [use-case walkthrough](docs/use-cases/dutch-it-job-market.md) for semantics and operational limits. Historical research is archived separately.
