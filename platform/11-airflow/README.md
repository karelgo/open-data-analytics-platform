# Daily Dutch IT job market

The only deployed example DAG is `dutch_it_jobs_daily`. It runs at **05:00
Europe/Amsterdam**, using the collection date from the end of its data interval.
Catchup is disabled and only one run may execute at a time.

1. Extract explicit `demo` or `live` sources and upload a successful date partition.
2. Launch Stackable Spark to atomically replace that Bronze Delta date partition.
3. Run `dbt build` (including data quality tests), then publish dbt artifacts.
4. Refresh the Trino catalog, dbt lineage/test results and metadata tags.
5. Register the seven Job Market BI datasets and publish the single dashboard.

`job-market-settings` defaults to `JOB_MARKET_MODE=demo`. For live Adzuna search,
create Secret `job-market-api-credentials` with `ADZUNA_APP_ID` and
`ADZUNA_APP_KEY`, and set the ConfigMap mode to `live`. The extractor never
falls back to fixtures when live extraction fails. The image contains the
source registry; rebuild it after changing approved feed/detail-page URLs.

Build/import `odap/job-market:dev` using `make jobs-image`, then deploy the
platform. For a registry image, set `JOB_MARKET_IMAGE` on the Airflow scheduler,
webserver and KubernetesExecutor envOverrides.

The repository's Stackable Airflow 3.0.6 setup has a previously observed
execution API integration issue. If task Pods cannot register, `make jobs-run`
executes the same extraction/Spark/dbt runtime as a standalone Kubernetes Job.
No successful cluster run is claimed without checking job and driver logs.

A lakehouse is pinned to either demo or live by `job-market/mode.json` in the
Bronze bucket. Use separate deployments to compare modes; a mode change requires
a deliberate reset of all job-market tables and objects. Successful extracts are
uploaded under immutable `raw/snapshot_date=DATE/attempts/UUID/` prefixes. The
date-root `current.json` pointer is published only after every upload succeeds.
Spark verifies that pointer, the success manifest, mode and record count before
replacing a Delta partition.
