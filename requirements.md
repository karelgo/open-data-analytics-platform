# Dutch IT Job Market requirements

1. One active use case covers Data, Cloud, SAP, AI, Software and Security jobs in the Netherlands.
2. Offline data is deterministic and explicitly synthetic; live source failures never silently produce demo data.
3. Daily observations preserve source identity, actual retrieval time, logical snapshot date, publication dates and source evidence.
4. Rerunning a date is idempotent. Cross-source deduplication is conservative, with source provenance retained.
5. Original salary units, currency, missing values and estimate flags remain visible. Annual EUR comparisons use only supported year/month values.
6. Daily absence is not interpreted as confirmed vacancy closure.
7. Spark, Trino, dbt, Airflow, Superset, OpenMetadata, Jupyter and the portal use the same job-market subject.
8. Raw payloads remain restricted; analytical descriptions redact contact details. No applicant profiles or candidate rankings are collected.
9. dbt tests gate downstream catalog/dashboard refresh. The reference does not provide atomic promotion of all mart updates.
10. Source permissions, bounded coverage, runtime configuration and validation limits are documented.

[Detailed specification](docs/use-cases/dutch-it-job-market.md).
