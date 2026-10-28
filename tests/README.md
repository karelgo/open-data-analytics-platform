# Platform verification

`make jobs-test` runs offline behavioral tests for the one supported Dutch IT job-market example. `make jobs-demo JOBS_DATE=2026-10-28` generates reproducible snapshots, SQLite views and dashboard JSON.

`make opa-test` checks research-purpose access, restricted bronze, unknown roles, writes, self-service grants and contact masking. `make dbt-parse` validates model syntax without Trino. `dbt build` in the cluster executes actual data tests before catalog publication.

`make e2e` runs the complete job-market pipeline against an existing cluster, then asserts populated bronze observations and gold inventory. `make smoke` additionally checks platform services. A missing job dataset fails the data smoke check; provision data with `make jobs-run` first.

No automated test contacts live job boards. Live source collection requires configured credentials or approved feeds.
