# Operate the Dutch IT job-market pipeline

This runbook covers the single active example. Shared platform infrastructure is described in [deployment modes](deployment-modes.md) and the component READMEs under `platform/`.

## Local verification

```bash
make jobs-demo
make jobs-test
```

Demo output defaults to `examples/dutch-it-jobs/output`; live Make runs default to `examples/dutch-it-jobs/output-live`. Keep modes separate. A live-source failure must not produce synthetic observations.

## Platform execution

```bash
make jobs-image
make jobs-run
```

Use Airflow DAG `dutch_it_jobs_daily` for scheduled execution at 05:00 Europe/Amsterdam. Confirm the runtime image exists in the cluster or registry. Choose demo or live before the first data run; the object-store `job-market/mode.json` marker pins the dataset to one mode. Switching requires a separately configured deployment or a deliberate complete dataset reset.

A source run writes immutable attempt objects beneath `job-market/raw/snapshot_date=YYYY-MM-DD/attempts/UUID/`. After the successful attempt is fully uploaded, a date-root `current.json` pointer publishes it for Spark. Inspect that pointer and its `manifest.json` before loading or comparing data. Failed attempts do not replace the last successful published attempt.

Spark validates the selected manifest and loads the daily Bronze partition. dbt builds and tests Silver/Gold before the pipeline is considered successful and before downstream catalog/dashboard refresh. Marts are materialized before tests run, so an existing dashboard may query updated tables while a build runs; no atomic all-mart promotion or rollback layer is implemented. Keep the source manifest and task logs when troubleshooting.

## Checks and incidents

| Symptom | Check |
|---|---|
| No daily run | Airflow scheduler, DAG pause state, execution image availability and timezone |
| Live extraction failed | Source credentials, configured URLs, HTTP status, retry limits and manifest errors |
| Counts unexpectedly lower | Same source/search configuration, pagination limits, successful manifest, duplicate groups and snapshot date |
| Gold not updated | Spark driver logs, Bronze snapshot partition, dbt build/test result |
| Dashboard empty | Gold table existence, Superset dataset registration, signed-in role and selected date |
| Catalog missing | Metadata service connectivity, job-market ingestion configuration and dbt artifacts |
| Access denied | Signed-in identity and OPA schema/purpose grants; request the minimum needed access |

A missing listing is not established closure. Never backfill an earlier observation date with today's live response and present it as historical truth. Retain original units and distinguish estimated pay from reported pay.

## Observability and recovery

Use Prometheus/Grafana for service health and OpenSearch for platform logs. Extraction manifests report source coverage; service health alone does not establish a complete extraction. Re-run the same logical date after a recoverable failure; partition replacement prevents duplicate daily observations.

Raw payloads remain restricted and are not included in the public portal sample. Back up object-store data and Hive Metastore together before environment changes, following your deployment's storage procedures. Avoid printing source API keys in logs or URLs.

[Full walkthrough](use-cases/dutch-it-job-market.md).
