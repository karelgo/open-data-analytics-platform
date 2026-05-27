"""Gold batch: silver.wia_spark.aanvraag → gold.uc01_wia_spark.funnel_daily.

Parallel-Spark equivalent van dbt's marts/uc01_claims_funnel/mart_uc01_claims_funnel_daily.
Aggregateert silver-aanvragen tot een daily funnel:

  per (aanvraag_datum, onderdeel, status):
    aantal                       (count)
    gem_arbeidsongeschikt_pct    (avg)
    distinct_regios              (approx_count_distinct)

Schemanaam `uc01_wia_spark` (i.p.v. dbt's `uc01_claims_funnel`) → naast elkaar.
Trino-pad: gold.uc01_wia_spark.funnel_daily.

Aanroep: via Airflow DAG transform_wia_spark (SparkApplication-template
platform/11-airflow/jobs/spark-gold-wia.yaml). Mode: full overwrite met
dynamicPartitionOverwrite — gold-tabel is volledig deterministisch
afgeleid uit silver, dus geen MERGE nodig.

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/stackable/spark/jobs")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from pyspark.sql import functions as F  # noqa: E402

from lakehouse_io import (  # noqa: E402
    TABLE_FORMAT,
    get_spark_with_lakehouse_config,
)

GOLD_BASE = os.getenv("GOLD_BASE", "s3a://odap-gold")
GOLD_SCHEMA = "uc01_wia_spark"
GOLD_TABLE = f"{GOLD_SCHEMA}.funnel_daily"
GOLD_PATH = f"{GOLD_BASE}/{GOLD_SCHEMA}/funnel_daily"

SOURCE_TABLE = "wia_spark.aanvraag"  # silver.wia_spark.aanvraag in Trino


def ensure_gold_schema(spark) -> None:
    """HMS-database uc01_wia_spark @ s3a://odap-gold/uc01_wia_spark/ (idempotent)."""
    spark.sql(
        f"CREATE SCHEMA IF NOT EXISTS {GOLD_SCHEMA} "
        f"LOCATION '{GOLD_BASE}/{GOLD_SCHEMA}/'"
    )


def main() -> int:
    spark = get_spark_with_lakehouse_config("batch-gold-claims")
    spark.sparkContext.setLogLevel("WARN")
    print(
        f"==> Gold batch start: source={SOURCE_TABLE} target={GOLD_TABLE} "
        f"format={TABLE_FORMAT}",
        flush=True,
    )

    ensure_gold_schema(spark)

    silver = spark.table(SOURCE_TABLE)
    in_cnt = silver.count()
    print(f"  Silver rows: {in_cnt}", flush=True)
    if in_cnt == 0:
        print("  Silver is leeg — run eerst silver-wia DAG-task.", flush=True)
        return 0

    funnel = (
        silver.groupBy("aanvraag_datum", "onderdeel", "status")
        .agg(
            F.count("*").alias("aantal"),
            F.round(F.avg("arbeidsongeschikt_pct"), 2).alias(
                "gem_arbeidsongeschikt_pct"
            ),
            F.approx_count_distinct("regio_code").alias("distinct_regios"),
        )
        .withColumn("gold_ingestion_ts", F.current_timestamp())
    )

    out_cnt = funnel.count()
    print(f"  Aggregated to {out_cnt} (datum, onderdeel, status)-rijen", flush=True)

    # Volledige overwrite — gold is deterministisch afgeleid uit silver.
    # DynamicPartitionOverwrite zou alleen geraakte partities overschrijven,
    # maar voor deze demo is full refresh transparanter.
    funnel.write.format(TABLE_FORMAT).mode("overwrite").partitionBy(
        "aanvraag_datum"
    ).option("overwriteSchema", "true").save(GOLD_PATH)

    # Idempotente HMS-registratie.
    spark.sql(f"DROP TABLE IF EXISTS {GOLD_TABLE}")
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {GOLD_TABLE} "
        f"USING DELTA LOCATION '{GOLD_PATH}'"
    )

    final_cnt = spark.table(GOLD_TABLE).count()
    print(
        f"  Gold klaar: {GOLD_TABLE} bevat {final_cnt} rijen ({GOLD_PATH})",
        flush=True,
    )
    # Korte preview voor de logs.
    print("  Top 5 funnel-rijen:", flush=True)
    spark.table(GOLD_TABLE).orderBy("aanvraag_datum", "onderdeel", "status").show(
        5, truncate=False
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
