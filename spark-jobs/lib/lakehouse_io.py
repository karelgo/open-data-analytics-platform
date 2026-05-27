"""Format-agnostische lakehouse I/O helper voor Spark.

Leest TABLE_FORMAT uit env (default 'delta'). Switching naar iceberg vergt
alleen `TABLE_FORMAT=iceberg` on the SparkApplication, geen code-wijziging
in calling jobs.

Requireden op Spark-image (via SparkApplication.deps.packages):
  - delta:    io.delta:delta-spark_2.12:3.2.x
  - iceberg:  org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.x
  - s3a:      hadoop-aws + aws-sdk-bundle (in Stackable-image meestal aanwezig)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

TABLE_FORMAT = os.getenv("TABLE_FORMAT", "delta").lower()
HMS_URI = os.getenv("HIVE_METASTORE_URI", "thrift://hive:9083")
S3_ENDPOINT = os.getenv(
    "S3_ENDPOINT", "http://minio.odap-platform.svc.cluster.local:9000"
)
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "platformadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_REGION = os.getenv("S3_REGION", "eu-nl-1")


def get_spark_with_lakehouse_config(app_name: str) -> "SparkSession":
    """Bouw SparkSession met format-aware Hive + S3A + table-format extensions."""
    from pyspark.sql import SparkSession  # noqa: PLC0415

    builder = (
        SparkSession.builder.appName(app_name)
        # Hive Metastore
        .config("spark.sql.catalogImplementation", "hive")
        .config("hive.metastore.uris", HMS_URI)
        # Performance
        .config("spark.sql.shuffle.partitions", "8")
    )

    # S3A — alleen overrides als de SparkApplication GEEN s3connection-ref
    # heeft (i.e. lokale dev runs zonder Stackable-controller). In cluster
    # injecteert `spark.stackable.tech_sparkapplication` al endpoint, ssl,
    # truststore en credentials from the S3Connection. Overrides hier
    # overschrijven die en breken TLS naar HTTPS-MinIO.
    if os.getenv("STACKABLE_S3_AUTOCONFIG", "true").lower() != "true":
        builder = (
            builder.config("spark.hadoop.fs.s3a.endpoint", S3_ENDPOINT)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
            .config("spark.hadoop.fs.s3a.access.key", S3_ACCESS_KEY)
            .config("spark.hadoop.fs.s3a.secret.key", S3_SECRET_KEY)
            .config(
                "spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
            )
        )

    if TABLE_FORMAT == "delta":
        builder = builder.config(
            "spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension"
        ).config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    elif TABLE_FORMAT == "iceberg":
        builder = (
            builder.config(
                "spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            )
            # spark_catalog upgraded zodat saveAsTable("bronze.demo.x") correct werkt
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.iceberg.spark.SparkSessionCatalog",
            )
            .config("spark.sql.catalog.spark_catalog.type", "hive")
        )
    else:
        raise ValueError(f"Onbekend TABLE_FORMAT: {TABLE_FORMAT!r}")

    return builder.getOrCreate()


def write_table(
    df: "DataFrame",
    table_name: str,
    mode: str = "append",
    partition_by: list[str] | None = None,
) -> None:
    """Schrijf een batch DataFrame naar Delta of Iceberg.

    `table_name` bv. 'bronze.persons.created'. Tabel wordt lazy gecreëerd.
    """
    writer = df.write.format(TABLE_FORMAT).mode(mode)
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.saveAsTable(table_name)


def write_stream_to_table(
    df: "DataFrame",
    table_name: str,
    checkpoint_path: str,
    mode: str = "append",
    partition_by: list[str] | None = None,
    trigger_seconds: int = 30,
):
    """Streaming write naar Delta/Iceberg tabel. Returnt StreamingQuery."""

    writer = (
        df.writeStream.format(TABLE_FORMAT)
        .option("checkpointLocation", checkpoint_path)
        .outputMode(mode)
        .trigger(processingTime=f"{trigger_seconds} seconds")
    )
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    return writer.toTable(table_name)


def ensure_bronze_schema(spark: "SparkSession") -> None:
    """Maak Hive-database `odap` aan voor bronze-Delta-tabellen (idempotent).

    Trino's `bronze` catalog mapt op deze Hive-metastore, dus Trino ziet
    `bronze.demo.<table>`. Spark spreekt 2-level (`<domain>.<table>`); de
    eerdere `CREATE SCHEMA bronze.uwv` faalde met
    `_LEGACY_ERROR_TEMP_1055` omdat Spark `bronze.uwv` als één
    database-naam met dot interpreteert (geen catalog-registratie voor
    `bronze` in spark_catalog).
    """
    spark.sql("CREATE SCHEMA IF NOT EXISTS uwv " "LOCATION 's3a://odap-bronze/demo/'")
