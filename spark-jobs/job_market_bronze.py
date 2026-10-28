"""Load a successful daily extract into an idempotent Delta snapshot partition."""

from __future__ import annotations

import os
from datetime import date

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T


def main():
    snapshot_date = date.fromisoformat(os.environ["SNAPSHOT_DATE"]).isoformat()
    if os.getenv("TABLE_FORMAT", "delta") != "delta":
        raise ValueError(
            "The job-market Spark loader currently requires TABLE_FORMAT=delta"
        )
    spark = (
        SparkSession.builder.appName("dutch-it-jobs-bronze")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.catalogImplementation", "hive")
        .config(
            "hive.metastore.uris",
            os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083"),
        )
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    strings = [
        "job_id",
        "source",
        "source_job_id",
        "canonical_url",
        "duplicate_group_id",
        "snapshot_date",
        "observed_at",
        "title",
        "company",
        "city",
        "province",
        "country_code",
        "description_text",
        "seniority",
        "employment_type",
        "contract_type",
        "work_mode",
        "salary_currency",
        "salary_period",
        "language",
        "education",
        "published_at",
        "expires_at",
    ]
    numbers = [
        "latitude",
        "longitude",
        "hours_min",
        "hours_max",
        "salary_min",
        "salary_max",
        "salary_year_min",
        "salary_year_max",
    ]
    schema = T.StructType(
        [T.StructField(n, T.StringType()) for n in strings]
        + [T.StructField(n, T.DoubleType()) for n in numbers]
        + [T.StructField(n, T.ArrayType(T.StringType())) for n in ["domains", "skills"]]
        + [
            T.StructField(n, T.BooleanType())
            for n in ["salary_is_estimated", "is_synthetic"]
        ]
    )
    bucket = os.getenv("BRONZE_BUCKET", "odap-bronze")
    base = f"s3a://{bucket}/job-market"
    pointer = (
        spark.read.option("multiLine", "true")
        .json(f"{base}/raw/snapshot_date={snapshot_date}/current.json")
        .first()
        .asDict()
    )
    mode = (
        spark.read.option("multiLine", "true").json(f"{base}/mode.json").first()["mode"]
    )
    prefix = pointer.get("attempt_prefix", "")
    expected_prefix = f"job-market/raw/snapshot_date={snapshot_date}/attempts/"
    if (
        pointer.get("snapshot_date") != snapshot_date
        or pointer.get("mode") != mode
        or mode not in ("demo", "live")
        or not prefix.startswith(expected_prefix)
        or ".." in prefix
    ):
        raise ValueError(
            "Current extract pointer has mismatched date, mode or object prefix"
        )
    manifest = (
        spark.read.option("multiLine", "true")
        .json(f"s3a://{bucket}/{prefix}/manifest.json")
        .first()
        .asDict()
    )
    if (
        manifest.get("status") != "success"
        or manifest.get("snapshot_date") != snapshot_date
        or manifest.get("mode") != mode
        or manifest.get("observation_count", 0) < 1
    ):
        raise ValueError("Extract manifest is unsuccessful, empty or mismatched")
    df = (
        spark.read.schema(schema)
        .option("mode", "FAILFAST")
        .json(f"s3a://{bucket}/{prefix}/normalized/observations.jsonl")
    )
    count = df.count()
    if count != manifest["observation_count"] or count != pointer.get(
        "observation_count"
    ):
        raise ValueError("Extract row count does not match the successful manifest")
    if (
        df.filter(
            F.col("snapshot_date").isNull()
            | (F.col("snapshot_date") != snapshot_date)
            | F.col("is_synthetic").isNull()
            | (F.col("is_synthetic") != (mode == "demo"))
        )
        .limit(1)
        .count()
    ):
        raise ValueError(
            "Extract rows have a mismatched date or synthetic/live provenance"
        )
    if df.groupBy("job_id").count().filter("count > 1").limit(1).count():
        raise ValueError("Duplicate job_id in daily source observations")
    path = f"s3a://{bucket}/job-market/observations"
    # replaceWhere atomically replaces only this date, so retries preserve history.
    (
        df.write.format("delta")
        .mode("overwrite")
        .partitionBy("snapshot_date")
        .option("replaceWhere", f"snapshot_date = '{snapshot_date}'")
        .save(path)
    )
    spark.sql(
        f"CREATE DATABASE IF NOT EXISTS job_market LOCATION 's3a://{bucket}/job-market/'"
    )
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS job_market.observations USING DELTA LOCATION '{path}'"
    )
    print(
        f"Loaded validated {snapshot_date} snapshot into bronze.job_market.observations",
        flush=True,
    )
    spark.stop()


if __name__ == "__main__":
    main()
