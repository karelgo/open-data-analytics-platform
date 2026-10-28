# Dutch IT job market transformations

The only active example is `dutch-it-job-market`. Spark registers
`bronze.job_market.observations`; `dbt build` creates validated Silver snapshots
and Gold marts. Run with `dbt build --profiles-dir .` against Trino.
The runtime image publishes `manifest.json`, `catalog.json`, and `run_results.json`
to `s3://odap-meta/dbt/latest/` for OpenMetadata.

All Trino catalogs share Hive Metastore, so table names are unique and each
persisted Gold table explicitly uses the Gold bucket. Domains are multi-label;
counts overlap. Snapshots are bounded observations, never national vacancy totals
or evidence that a missing advertisement has closed.
