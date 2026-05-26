# spark-jobs

PySpark-jobs voor het ODAP platform.

| Bestand | Doel |
|---|---|
| [`lib/lakehouse_io.py`](lib/lakehouse_io.py) | Format-agnostische helper. Leest `TABLE_FORMAT` env; bouwt SparkSession met Hive Metastore + S3A + Delta/Iceberg extensions. |
| [`streaming_files_to_lakehouse.py`](streaming_files_to_lakehouse.py) | File-source streaming: leest JSONL uit `s3a://odap-raw/<domain>/<entity>/dt=…/` en schrijft per stream naar `bronze.uwv.<domain>_<entity>` via `foreachBatch`. |
| `batch_polisadm_load.py` | TBD fase 5 — batch-ingest van staging-bestanden. |
| `ml_wajong_features.py` | TBD fase 9+ — feature engineering UC-02 placeholder. |
| `lakehouse_maintenance.py` | TBD fase 6 — Delta `OPTIMIZE`/`VACUUM` (Iceberg `expire_snapshots`). |

## Deployment

De scripts worden via `kustomize configMapGenerator` gemount in de
SparkApplication-pods (zie [`platform/08-spark/`](../platform/08-spark/)).
`scripts/deploy-platform.sh` synchroniseert deze map naar
`platform/08-spark/scripts/` (gitignored) zodat kustomize ze van een
toegestane root-pad kan oppikken.

## Lokaal draaien (zonder cluster)

```bash
cd spark-jobs
TABLE_FORMAT=delta python3 -c "import lib.lakehouse_io as m; print(m.TABLE_FORMAT)"
```

End-to-end testen vereist HMS + MinIO (met `odap-raw` + `odap-bronze` buckets); doe dat in de cluster.

## Format-switch

Wijzig in [`platform-config.yaml`](../platform-config.yaml) en
herapply de SparkApplication. De Spark-driver leest `TABLE_FORMAT` env
en gebruikt automatisch de juiste extension + connector.
