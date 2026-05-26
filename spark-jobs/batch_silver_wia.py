"""Silver batch: bronze.uwv.wia_aanvraag → silver.wia_spark.aanvraag.

Pure-Spark equivalent van dbt's models/staging/wia/stg_wia_aanvraag.sql.
Parseert JSON-envelope uit bronze.payload naar typed Delta-tabel; idempotent
via Delta MERGE op aanvraag_id (toont een Delta-specifieke feature die
Parquet niet kan).

Schemanaam `wia_spark` (i.p.v. dbt's `wia`) zodat beide paden naast elkaar
kunnen bestaan. Trino-pad: silver.wia_spark.aanvraag.

Aanroep: via Airflow DAG transform_wia_spark (SparkApplication-template
platform/11-airflow/jobs/spark-silver-wia.yaml).

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/stackable/spark/jobs")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    DateType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from lakehouse_io import (  # noqa: E402
    TABLE_FORMAT,
    get_spark_with_lakehouse_config,
)

SILVER_BASE = os.getenv("SILVER_BASE", "s3a://odap-silver")
SILVER_SCHEMA = "wia_spark"
SILVER_TABLE = f"{SILVER_SCHEMA}.aanvraag"
SILVER_PATH = f"{SILVER_BASE}/{SILVER_SCHEMA}/aanvraag"

SOURCE_TABLE = "uwv.wia_aanvraag"  # bronze.uwv.wia_aanvraag in Trino

# Schema voor from_json — moet matchen met seed-payload-envelope.
PAYLOAD_SCHEMA = StructType(
    [
        StructField(
            "payload",
            StructType(
                [
                    StructField("aanvraag_id", StringType(), True),
                    StructField("bsn", StringType(), True),
                    StructField("aanvraag_datum", DateType(), True),
                    StructField("eerste_ziektedag", DateType(), True),
                    StructField("onderdeel", StringType(), True),
                    StructField("regio_code", StringType(), True),
                    StructField("status", StringType(), True),
                    StructField("arbeidsongeschikt_pct", IntegerType(), True),
                ]
            ),
            True,
        ),
    ]
)


def ensure_silver_schema(spark) -> None:
    """HMS-database wia_spark @ s3a://odap-silver/wia_spark/ (idempotent)."""
    spark.sql(
        f"CREATE SCHEMA IF NOT EXISTS {SILVER_SCHEMA} "
        f"LOCATION '{SILVER_BASE}/{SILVER_SCHEMA}/'"
    )


def main() -> int:
    from pyspark.sql import Window  # noqa: PLC0415

    spark = get_spark_with_lakehouse_config("batch-silver-wia")
    spark.sparkContext.setLogLevel("WARN")
    print(
        f"==> Silver batch start: source={SOURCE_TABLE} target={SILVER_TABLE} "
        f"format={TABLE_FORMAT}",
        flush=True,
    )

    ensure_silver_schema(spark)

    bronze = spark.table(SOURCE_TABLE)
    in_cnt = bronze.count()
    print(f"  Bronze rows: {in_cnt}", flush=True)
    if in_cnt == 0:
        print("  Bronze is leeg — geen werk. Run eerst seed-bronze-wia.", flush=True)
        return 0

    parsed = bronze.withColumn("env", F.from_json("payload", PAYLOAD_SCHEMA))
    typed = (
        parsed.select(
            F.col("env.payload.aanvraag_id").alias("aanvraag_id"),
            F.col("env.payload.bsn").alias("bsn"),
            F.col("env.payload.aanvraag_datum").alias("aanvraag_datum"),
            F.col("env.payload.eerste_ziektedag").alias("eerste_ziektedag"),
            F.col("env.payload.onderdeel").alias("onderdeel"),
            F.col("env.payload.regio_code").alias("regio_code"),
            F.col("env.payload.status").alias("status"),
            F.col("env.payload.arbeidsongeschikt_pct").alias("arbeidsongeschikt_pct"),
            F.col("source_ts").alias("ingestion_source_ts"),
            F.col("event_date"),
        )
        .filter(F.col("aanvraag_id").isNotNull())
    )

    # Dedupe op aanvraag_id (laatste event wint).
    dedup_w = Window.partitionBy("aanvraag_id").orderBy(
        F.col("ingestion_source_ts").desc_nulls_last()
    )
    deduped = (
        typed.withColumn("_rn", F.row_number().over(dedup_w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .withColumn("silver_ingestion_ts", F.current_timestamp())
    )
    out_cnt = deduped.count()
    print(f"  After parse + dedupe: {out_cnt} unique aanvragen", flush=True)

    # Delta MERGE — toont Delta-superpower vs Parquet. Op eerste run schrijven
    # we de tabel + registreren; daarna upsert per aanvraag_id.
    from delta.tables import DeltaTable  # noqa: PLC0415

    if DeltaTable.isDeltaTable(spark, SILVER_PATH):
        print("  Bestaande Delta-tabel — voer MERGE uit", flush=True)
        (
            DeltaTable.forPath(spark, SILVER_PATH)
            .alias("t")
            .merge(deduped.alias("s"), "t.aanvraag_id = s.aanvraag_id")
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
    else:
        print("  Verse tabel — initial write + HMS-registratie", flush=True)
        deduped.write.format(TABLE_FORMAT).mode("append").partitionBy(
            "event_date"
        ).save(SILVER_PATH)
        # Drop legacy non-Delta registratie indien aanwezig (zie bronze-job
        # voor zelfde idempotency-truc).
        spark.sql(f"DROP TABLE IF EXISTS {SILVER_TABLE}")
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {SILVER_TABLE} "
            f"USING DELTA LOCATION '{SILVER_PATH}'"
        )

    final_cnt = spark.table(SILVER_TABLE).count()
    print(
        f"  Silver klaar: {SILVER_TABLE} bevat nu {final_cnt} rijen "
        f"({SILVER_PATH})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
