"""Stream JSONL files uit S3 raw zone → bronze.<domain>.<entity> Delta/Iceberg.

Vervangt streaming_kafka_to_lakehouse.py. Spark Structured Streaming leest
`s3a://odap-raw/<domain>/<entity>/dt=<YYYY-MM-DD>/*.jsonl` als text-stream.
Iedere regel is een raw event-envelope (JSON). De `stream`-identifier wordt
uit het bestandspad afgeleid.

Bronze schema (per tabel `bronze.demo.<domain>_<entity>`):
  payload      (string)    raw JSON envelope, ongewijzigd
  stream       (string)    bv. 'customers.created' — afgeleid uit pad
  source_file  (string)    volledige S3-URL van bron-bestand
  source_ts    (timestamp) event-tijd (vooralsnog = ingestion_ts)
  ingestion_ts (timestamp) Spark-schrijfmoment
  event_date   (date)      partition key

dbt staging-models in fase 5 parsen `payload` naar getypte silver-tabellen.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, "/stackable/spark/jobs")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from pyspark.sql import functions as F  # noqa: E402

from lakehouse_io import (  # noqa: E402
    TABLE_FORMAT,
    ensure_bronze_schema,
    get_spark_with_lakehouse_config,
)

RAW_PATH = os.getenv("RAW_PATH", "s3a://odap-raw/")
CHECKPOINT_BASE = os.getenv("CHECKPOINT_BASE", "s3a://odap-checkpoints/streaming")
TRIGGER_SECONDS = int(os.getenv("TRIGGER_SECONDS", "20"))

# Verwacht pad: s3a://odap-raw/<stream-segments>/dt=<date>/part-*.jsonl
# bv. customers/created/dt=...  → stream 'customers.created'.
_STREAM_PATH_RE = re.compile(r"/odap-raw/(?P<path>.+?)/dt=")


def stream_to_table(stream: str) -> str | None:
    """`customers.created` → `<domain>.person_created` (Hive db=uwv, table=…).

    Trino ziet deze als `bronze.demo.<table>` via de bronze-catalog.
    Returnt None voor onverwachte stream-naming.
    """
    parts = stream.split(".")
    if len(parts) < 3 or parts[0] != "demo":
        return None
    domain, *entity_parts = parts[1:]
    entity = "_".join(entity_parts)
    return f"uwv.{domain}_{entity}"


def _extract_stream_from_path(file_path: str) -> str | None:
    """Haal stream-naam uit S3-pad. None als pad niet voldoet."""
    m = _STREAM_PATH_RE.search(file_path or "")
    if not m:
        return None
    return m.group("path").replace("/", ".")


BRONZE_BASE = os.getenv("BRONZE_BASE", "s3a://odap-bronze/uwv")


def process_batch(batch_df, batch_id: int) -> None:
    """foreachBatch dispatcher — groepeer per stream, schrijf per tabel.

    We schrijven Delta files direct naar een S3-pad (`.save(path)`) i.p.v.
    `saveAsTable(name)`. Dat omzeilt diverse Hive/Delta metastore-edge-cases
    op een verse cluster (DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION op een
    nochtans lege bucket; legacy non-Delta registraties van Hive). Na de
    eerste write registreren we de tabel met `CREATE TABLE IF NOT EXISTS
    ... USING DELTA LOCATION` zodat Trino hem ziet. Idempotent op
    latere batches.
    """
    if batch_df.rdd.isEmpty():
        return
    spark = batch_df.sparkSession
    streams = [
        r["stream"]
        for r in batch_df.select("stream").distinct().collect()
        if r["stream"] is not None
    ]
    for stream in streams:
        table = stream_to_table(stream)
        if table is None:
            print(
                f"  [batch {batch_id}] skip onbekende stream-format: {stream}",
                flush=True,
            )
            continue
        # `table` = "uwv.person_created" -> entity = "person_created"
        entity = table.split(".", 1)[1]
        path = f"{BRONZE_BASE}/{entity}"
        stream_df = batch_df.filter(F.col("stream") == F.lit(stream))
        out_df = stream_df.drop("stream")
        out_df.write.format(TABLE_FORMAT).mode("append").save(path)
        # Idempotente registratie. Hive-table-not-Delta restanten worden
        # eerst gedropt zodat de nieuwe registratie schoon kan landen.
        spark.sql(f"DROP TABLE IF EXISTS {table}")
        spark.sql(f"CREATE TABLE IF NOT EXISTS {table} USING DELTA LOCATION '{path}'")
        cnt = stream_df.count()
        print(
            f"  [batch {batch_id}] {stream} → {table} ({path}): {cnt} rows", flush=True
        )


def main() -> int:
    spark = get_spark_with_lakehouse_config("streaming-files-to-bronze")
    spark.sparkContext.setLogLevel("WARN")
    print(
        f"==> Streaming start (TABLE_FORMAT={TABLE_FORMAT}, raw_path={RAW_PATH})",
        flush=True,
    )

    ensure_bronze_schema(spark)

    # UDF om stream-naam uit pad te halen. Single-shot, geen state.
    extract_stream_udf = F.udf(_extract_stream_from_path)

    raw = (
        spark.readStream.format("text")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "*.jsonl")
        .load(RAW_PATH)
    )

    enriched = (
        raw.withColumnRenamed("value", "payload")
        .withColumn("source_file", F.input_file_name())
        .withColumn("stream", extract_stream_udf(F.col("source_file")))
        .withColumn("ingestion_ts", F.current_timestamp())
        .withColumn("source_ts", F.col("ingestion_ts"))
        .withColumn("event_date", F.to_date("source_ts"))
        .select(
            "payload",
            "stream",
            "source_file",
            "source_ts",
            "ingestion_ts",
            "event_date",
        )
    )

    query = (
        enriched.writeStream.foreachBatch(process_batch)
        .option("checkpointLocation", f"{CHECKPOINT_BASE}/files-to-bronze")
        .trigger(processingTime=f"{TRIGGER_SECONDS} seconds")
        .start()
    )

    print(f"  Streaming query started: id={query.id} runId={query.runId}", flush=True)
    query.awaitTermination()
    return 0


if __name__ == "__main__":
    sys.exit(main())
