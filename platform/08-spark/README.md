# 08-spark

Spark on Kubernetes via Stackable's `SparkApplication` CRD.

| Resource | Doel |
|---|---|
| `SparkApplication streaming-bronze` | Structured Streaming: leest JSONL uit `s3a://odap-raw/`, schrijft naar Delta bronze (foreachBatch dispatcher per stream). |
| `ConfigMap spark-streaming-jobs` (gegenereerd) | Mount van `streaming_files_to_lakehouse.py` + `lakehouse_io.py`. |
| `SparkHistoryServer history` | Permanente Spark-UI op port 18080. Leest event-logs van alle voltooide jobs uit `s3a://odap-checkpoints/spark-events/`. Bereikbaar via `https://spark.<domain>/`. |
| `Job spark-events-prefix-init` | One-shot bij deploy: maakt `spark-events/.keep` placeholder in MinIO zodat history-server kan starten (S3 heeft geen leeg-directory concept). |

## Architectuur

```
data-generation/load_to_s3.py  →  s3://odap-raw/<domain>/<entity>/dt=YYYY-MM-DD/*.jsonl
                                              ↓ (Spark file source)
                                  streaming_files_to_lakehouse.py
                                              ↓
                                  bronze.demo.<domain>_<entity>  (Delta)
```

Geen message bus tussen producer en consumer — MinIO IS de buffer + replay-laag.

## Code-locatie

Canonical bron: [`spark-jobs/`](../../spark-jobs/) — daar staan
`streaming_files_to_lakehouse.py` en `lib/lakehouse_io.py`.

`scripts/deploy-platform.sh` kopieert deze bestanden naar
`platform/08-spark/scripts/` (gitignored) zodat kustomize ze via
`configMapGenerator` kan oppikken — zonder load-restrictor=None.

## Voorvereisten

- `platform/01-secrets/` — `minio-s3-credentials` Secret aanwezig.
- `platform/03-storage/` — `S3Connection s3-minio`; bucket `odap-raw` bestaat in MinIO.
- `platform/05-hive-metastore/` — HMS Ready.

## Apply

```bash
make deploy-platform   # incl. spark-jobs/ → platform/08-spark/scripts/ sync
# of stand-alone:
kubectl apply -k platform/08-spark/
```

## Validatie

```bash
kubectl -n odap-platform get sparkapplication
kubectl -n odap-platform logs -l app.kubernetes.io/instance=streaming-bronze --tail=50
```

In Spark UI: lijst van actieve streaming queries en batch-stats.

## Stream → tabel mapping

| File-pad | Bronze-tabel |
|---|---|
| `s3a://odap-raw/demo/persona/created/...` | `bronze.persons.created` |
| `s3a://odap-raw/demo/polisadm/ikv/...` | `bronze.policies.holders` |
| `s3a://odap-raw/demo/ww/aanvraag/...` | `bronze.service_requests.application` |
| `s3a://odap-raw/demo/wia/aanvraag/...` | `bronze.claims.application` |
| `s3a://odap-raw/demo/wajong/dossier/...` | `bronze.eligibility_cases.case` |
| `s3a://odap-raw/demo/zw/melding/...` | `bronze.incidents.report` |
| `s3a://odap-raw/demo/crm/contact/...` | `bronze.customers.interaction` |
| `s3a://odap-raw/demo/fez/claim_cost/...` | `bronze.finance.expense` |

## Format-switch

`TABLE_FORMAT` env staat in `streaming-bronze.yaml` op `"delta"`. Voor
Iceberg: wijzig `platform-config.yaml` + de twee env-blokken (driver +
executor).

## Productie

- `replicas: ≥ 3` op executor.
- Aparte SparkApplication per stream-domein (i.p.v. één foreachBatch dispatcher).
- Fault-tolerant execution + retry-policy.
- Delta Lake `OPTIMIZE` schedule + `VACUUM RETAIN 168 HOURS` via maintenance-DAG.

---

## WIA bronze→silver→gold demo (parallel-Spark-pad, naast dbt)

Een volledig pure-Spark + Delta Lake pad voor één vertical slice
(WIA-aanvragen), bedoeld om het Spark-verhaal van bronze tot goud
te demonstreren **naast** het bestaande dbt-+-Trino-pad voor silver/gold.
Beide paden schrijven naar dezelfde MinIO-buckets maar gebruiken aparte
HMS-schemas, dus ze raken elkaar niet.

### Naamgeving

| Laag    | dbt-pad (bestaand)                          | Spark-pad (demo)                          |
|---------|---------------------------------------------|-------------------------------------------|
| bronze  | `bronze.claims.application`                   | `bronze.claims.application` (gedeeld)       |
| silver  | `silver.claims.stg_claim_application`               | `silver.wia_spark.aanvraag`               |
| gold    | `gold.uc01_claims_funnel.mart_uc01_claims_funnel_daily` | `gold.uc01_wia_spark.funnel_daily` |
| S3-pad  | `s3a://odap-silver/wia/...`                  | `s3a://odap-silver/wia_spark/...`          |

### Componenten

| Bestand | Doel |
|---|---|
| [`spark-jobs/seed_bronze_claims.py`](../../spark-jobs/seed_bronze_claims.py) | Schrijft 200 synthetische WIA-rijen direct in bronze-Delta (omdat `streaming-bronze` uit staat). |
| [`apps/seed-bronze-claims.yaml`](apps/seed-bronze-claims.yaml) | One-shot SparkApplication; bewust NIET in `kustomization.yaml`. |
| [`spark-jobs/batch_silver_claims.py`](../../spark-jobs/batch_silver_claims.py) | Parse JSON-payload → typed Delta. Idempotent via Delta MERGE op `application_id`. |
| [`spark-jobs/batch_gold_claims.py`](../../spark-jobs/batch_gold_claims.py) | Aggregeert silver tot daily funnel (count, avg %, distinct regios) per (datum, onderdeel, status). |
| [`platform/11-airflow/jobs/spark-silver-wia.yaml`](../11-airflow/jobs/spark-silver-wia.yaml) | SparkApplication-template, gemount in `airflow-jobs` CM. `${RUN_ID}` placeholder. |
| [`platform/11-airflow/jobs/spark-gold-wia.yaml`](../11-airflow/jobs/spark-gold-wia.yaml) | Idem voor gold. |
| [`platform/11-airflow/dags/transform_wia_spark.py`](../11-airflow/dags/transform_wia_spark.py) | DAG met 2 KPO-tasks die `sed | kubectl apply` doen + `.status.phase` pollen. |
| [`platform/11-airflow/spark-launcher-rbac.yaml`](../11-airflow/spark-launcher-rbac.yaml) | SA `spark-launcher` + Role: sparkapplications CRUD + pods get/log. |

### Stappen om te draaien

```bash
# 1. Deploy het platform (sync van spark-jobs/, regenereer ConfigMaps, RBAC).
make deploy-platform

# 2. End-to-end Spark pipeline: seed → silver → gold (één commando).
make wia-spark-demo
# Of bestaande bronze hergebruiken:
# SKIP_SEED=1 make wia-spark-demo

# 3. Verifieer eindresultaat via Trino (zie laatste regels van make-output).
```

### Waarom geen Airflow DAG voor de orchestratie?

De DAG `transform_wia_spark` BESTAAT in de repo
([dags/transform_wia_spark.py](../11-airflow/dags/transform_wia_spark.py))
en is structureel correct, maar **werkt niet op SDP-26.3 / Airflow 3.0.6**:
de Stackable Airflow-image mist het `/execution/` API-endpoint dat task-pods
nodig hebben om hun TaskInstance te registreren. Geen enkele DAG runt sinds
2026-05-18. Zie `memory/feedback_stackable_airflow3_execution_api_missing.md`.

`scripts/wia-spark-demo.sh` (achter `make wia-spark-demo`) doet exact wat de
DAG zou doen — applies SparkApplications, polled `.status.phase`, ketens
silver→gold — maar zonder Airflow. Zodra de Stackable-bug gefixt is werkt
de DAG zonder code-wijziging.

### Waarom seed i.p.v. streaming-bronze?

`streaming-bronze` staat uit sinds [incident 2026-05-15](kustomization.yaml#L14-L18).
Voor deze demo prefereren we deterministische input boven het oplossen van
het streaming-resource-probleem — dat is een aparte opdracht. Zodra
streaming-bronze terug aan staat, kan de seed-stap overgeslagen worden;
de silver+gold DAG werkt onveranderd op de daadwerkelijke bronze-tabel.

### Resource-eisen (lessons learned op k3d, 2026-05-24)

| Setting | Waarde | Reden |
|---|---|---|
| `driver.memory.limit` | `1500Mi` | Onder ~1.2Gi crasht Spark met `INVALID_DRIVER_MEMORY` — System memory < 472MB minimum. |
| `executor.memory.limit` | `1500Mi` | Idem voor executor (`INVALID_EXECUTOR_MEMORY`). |
| `enableVectorAgent` | `false` | Vector aggregator ConfigMap bestaat niet op deze cluster; `true` blokkeert SparkApplication-reconcile met `VectorAggregatorConfigMapMissing`. |
| `seed`-write | géén `partitionBy` | Bestaande `s3a://odap-bronze/demo/claim_application/` Delta-tabel is niet-gepartitioneerd (streaming-bronze conventie); append met partitionering geeft `_LEGACY_ERROR_TEMP_DELTA_0007`. |

Failure-debugging tip: Stackable-operator delete'd driver-pod direct bij
`Failed` ongeacht `spark.kubernetes.driver.deleteOnTermination`. Voor logs:
tail `kubectl logs <driver-pod>` *terwijl* de pod nog Running is (snapshot
polling, niet `-f` — die mist de laatste seconden bij delete).

### Waarom MERGE in silver maar OVERWRITE in gold?

- **Silver** is een 1:1-projectie van bronze; `MERGE` op `application_id` toont
  een Delta-superpower (upsert op object-id, niet beschikbaar in raw
  Parquet) en is correct voor incrementele runs.
- **Gold** is een deterministische aggregatie; volledige overwrite is
  transparanter en de tabel is klein. In productie zou je
  `dynamicPartitionOverwrite` per `aanvraag_datum` willen.

### Vergelijking met dbt-pad

| Aspect | dbt | Spark |
|---|---|---|
| Taal | SQL (Trino dialect) | PySpark (DataFrame API) |
| Idempotentie | `materialized=view` (re-query) | Delta MERGE / overwrite |
| Orchestratie | Cosmos-tasks per model | Airflow KPO + kubectl-apply per SparkApplication |
| Trigger | Dataset-outlet van bronze-watch | Handmatig (demo) of Dataset (productie) |
| Compute | Trino-cluster (lange leven) | Spark driver+executor per run (kort leven) |
| Beste use case | SQL-transformaties, BI | Complex Python, ML-feature-engineering, MERGE |
