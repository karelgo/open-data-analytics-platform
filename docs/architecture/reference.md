# Reference implementation acceptance criteria

The active reference is [Dutch IT Job Market](../use-cases/dutch-it-job-market.md). Earlier unrelated business demonstrations are archived.

## Definition of Done

1. The offline fixture covers all six job domains and creates repeatable daily observations with explicit synthetic markers.
2. Live mode reports source failures and coverage without silently using fixtures.
3. Spark, Trino and dbt preserve source provenance, dated snapshots, salary units and conservative deduplication.
4. Gold tests run before the daily pipeline completes successfully.
5. Superset, Jupyter and OpenMetadata use the same `job_market` tables.
6. Analysts can read allowed Gold assets, while raw evidence remains restricted.
7. Schedule, credentials, source limitations and local checks are documented.

This reference is not a production readiness certification. Actual source connectivity and deployed service behavior require environment-level validation.
