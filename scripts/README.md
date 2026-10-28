# Platform scripts

The supported example entrypoints are `make jobs-demo` (local synthetic history), `make jobs-live` (configured API/approved feeds), `make jobs-image` (packaged runtime), and `make jobs-run` (existing Kubernetes platform). `seed.sh` is a compatibility alias for `job-market-cluster.sh`; it no longer generates unrelated personal-data examples.

`job-market-cluster.sh` runs extraction, Spark Bronze, dbt/tests, catalog/lineage enrichment and dashboard refresh. It reports failures through Job status and logs. It neither provisions infrastructure nor contacts live sources unless live mode is explicitly configured.

The remaining helpers deploy, configure and inspect reusable platform infrastructure. Historical use-case scripts have been retired. See [the runbook](../docs/runbook.md) and [job-market walkthrough](../docs/use-cases/dutch-it-job-market.md).
