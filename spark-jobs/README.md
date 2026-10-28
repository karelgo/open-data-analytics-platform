# Dutch IT jobs — Bronze Delta ingestion

`job_market_bronze.py` is the active Spark job. It reads the successful extract
at `s3://odap-bronze/job-market/raw/snapshot_date=YYYY-MM-DD/normalized/observations.jsonl`,
validates the grain and date, and atomically replaces only that date's Delta
partition. Rerunning does not duplicate jobs or erase older days.

Airflow `dutch_it_jobs_daily` and `make jobs-run` launch the same Stackable
SparkApplication through `infrastructure/job-market/runtime.py`. The job requires
Delta Lake; the current example does not claim an equivalent Iceberg execution path.

A lakehouse is pinned to either demo or live by `job-market/mode.json` in the
Bronze bucket. Use separate deployments to compare modes; a mode change requires
a deliberate reset of all job-market tables and objects. Successful extracts are
uploaded under immutable `raw/snapshot_date=DATE/attempts/UUID/` prefixes. The
date-root `current.json` pointer is published only after every upload succeeds.
Spark verifies that pointer, the success manifest, mode and record count before
replacing a Delta partition.
