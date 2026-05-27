"""Seed-script: vult bronze.claims.application met N synthetische rijen.

Bedoeld als one-shot voorbereiding for the Spark-bronze→silver→gold demo
(parallel aan dbt). De reguliere streaming-bronze SparkApplication staat
uit (zie incident 2026-05-15 in platform/08-spark/kustomization.yaml),
dus we vullen bronze direct vanuit een batch-job.

De envelope-structuur matcht wat dbt's stg_claim_application verwacht
($.payload.<veld>), zodat zowel het dbt- als het Spark-pad er tegelijk
mee kan werken.

Apply:
    kubectl apply -f platform/08-spark/apps/seed-bronze-claims.yaml

Status:
    kubectl -n odap-platform get sparkapplication seed-bronze-claims -w

Output:
    bronze.claims.application (Trino) / claims.application (Spark/HMS)

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

import json
import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, "/stackable/spark/jobs")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from pyspark.sql import Row  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    DateType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from lakehouse_io import (  # noqa: E402
    TABLE_FORMAT,
    ensure_bronze_schema,
    get_spark_with_lakehouse_config,
)

N_ROWS = int(os.getenv("SEED_ROWS", "200"))
BRONZE_BASE = os.getenv("BRONZE_BASE", "s3a://odap-bronze/uwv")
TABLE = "claims.application"
PATH = f"{BRONZE_BASE}/claim_application"

ONDERDELEN = ["WIA-IVA", "WIA-WGA"]
STATUSSEN = ["ingediend", "in_behandeling", "toegekend", "afgewezen"]
REGIOS = ["NH", "ZH", "UT", "GE", "OV", "GR", "FR", "DR", "FL", "NB", "ZL", "LB"]

# Vaste seed → reproduceerbare demo-data.
random.seed(20260524)


def _mk_payload(i: int, today: date) -> str:
    aanvraag_dt = today - timedelta(days=random.randint(0, 90))
    ziekte_dt = aanvraag_dt - timedelta(days=730 + random.randint(-30, 30))
    inner = {
        "application_id": f"WIA-{2026000000 + i}",
        "bsn": f"{random.randint(100000000, 999999999)}",
        "aanvraag_datum": aanvraag_dt.isoformat(),
        "eerste_ziektedag": ziekte_dt.isoformat(),
        "onderdeel": random.choice(ONDERDELEN),
        "regio_code": random.choice(REGIOS),
        "status": random.choices(STATUSSEN, weights=[20, 40, 30, 10])[0],
        "arbeidsongeschikt_pct": random.choice([35, 45, 55, 65, 80, 100]),
    }
    envelope = {
        "schema": "claims.application.v1",
        "event_id": str(uuid.uuid4()),
        "event_ts": datetime.combine(
            aanvraag_dt, datetime.min.time(), tzinfo=timezone.utc
        ).isoformat(),
        "payload": inner,
    }
    return json.dumps(envelope, ensure_ascii=False)


def _ensure_wia_schema_compat(spark) -> None:
    """Drop legacy non-Delta registratie als die er staat (idempotent)."""
    spark.sql(f"DROP TABLE IF EXISTS {TABLE}")


def main() -> int:
    spark = get_spark_with_lakehouse_config("seed-bronze-claims")
    spark.sparkContext.setLogLevel("WARN")
    print(
        f"==> Seed start: rows={N_ROWS} format={TABLE_FORMAT} path={PATH}",
        flush=True,
    )

    ensure_bronze_schema(spark)
    _ensure_wia_schema_compat(spark)

    today = date.today()
    now = datetime.now(timezone.utc)
    source_file = (
        f"s3a://odap-raw/demo/wia/aanvraag/dt={today.isoformat()}/seed-{uuid.uuid4()}.jsonl"
    )

    rows = [
        Row(
            payload=_mk_payload(i, today),
            source_file=source_file,
            source_ts=now,
            ingestion_ts=now,
            event_date=today,
        )
        for i in range(N_ROWS)
    ]
    schema = StructType(
        [
            StructField("payload", StringType(), False),
            StructField("source_file", StringType(), False),
            StructField("source_ts", TimestampType(), False),
            StructField("ingestion_ts", TimestampType(), False),
            StructField("event_date", DateType(), False),
        ]
    )
    df = spark.createDataFrame(rows, schema=schema)

    # Schrijf rechtstreeks naar S3-pad i.p.v. saveAsTable — zelfde reden als
    # streaming_files_to_lakehouse.py (vermijdt diverse Hive/Delta first-write
    # edge-cases op een verse cluster).
    #
    # Geen partitionBy — match conventie van streaming_files_to_lakehouse.py.
    # Bestaande Delta-tabel op dit pad heeft GEEN partition cols; append met
    # partitionBy("event_date") crasht met _LEGACY_ERROR_TEMP_DELTA_0007.
    df.write.format(TABLE_FORMAT).mode("append").save(PATH)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {TABLE} USING DELTA LOCATION '{PATH}'")

    cnt = spark.table(TABLE).count()
    print(f"  Seed klaar: {TABLE} bevat nu {cnt} rijen ({PATH})", flush=True)
    # Expliciete shutdown — anders blijven py4j-threads hangen en exit Spark
    # met code 1 ondanks succesvolle write. Silver/gold-jobs ondervinden dit
    # niet omdat ze geen Python-side createDataFrame doen.
    spark.stop()
    print("  SparkSession stopped — exit 0", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
