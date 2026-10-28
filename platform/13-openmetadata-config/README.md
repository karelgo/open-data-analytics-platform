# Dutch IT Job Market catalog

The single data product is `dutch_it_job_market` in the `JobMarket` domain. Bootstrap creates definitions, classifications, the owning team and glossary terms. It does not create fictitious table entities. Trino ingestion discovers actual Bronze/Silver/Gold `job_market` relations after the pipeline materializes them.

`services/dbt-workflow.yaml` reads `s3://odap-meta/dbt/latest/` for manifest, catalog and test results. Metadata enrichment maps resolved dbt ownership, purpose, source-permission requirements, glossary and domain onto those actual tables. `test-suites.yaml` describes the source-observation checks; executable mart tests live in dbt. Post-build metadata refresh imports dbt test results.

The Airflow DAG and manual job-market runner perform catalog ingestion, dbt lineage ingestion and enrichment after dbt tests succeed. Raw source responses are stored under restricted `odap-bronze/job-market/raw/` immutable attempt prefixes. Normalized rows redact common contacts; automatic redaction is not a guarantee that all personal information is removed. Review live publisher content before distributing it.

Existing unrelated tables from an older deployment are not deleted automatically. Start with a fresh example environment or retire old data and catalog entities deliberately before claiming a clean single-use-case instance. The repository no longer schedules or synthesizes those examples.

See [the end-to-end walkthrough](../../docs/use-cases/dutch-it-job-market.md).
