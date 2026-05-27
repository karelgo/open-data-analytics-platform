#!/usr/bin/env python3
"""CSV → bronze Delta loader.

Draait in een KubernetesPodOperator (zie csv_ingest_factory.py).

Stappen:
  1. Lees source-YAML uit /opt/odap/airflow/sources/<name>.yml
  2. Download CSV uit s3://<staging_bucket>/<object_key>
  3. Valideer schema + cast types via pyarrow
  4. Voeg metadata-kolommen toe (ingestion_ts, source_file, event_date)
  5. Schrijf Delta naar s3a://odap-bronze/demo/<table>/ (append, partitioned by event_date)
  6. Registreer Delta-tabel in Hive Metastore via Trino `system.register_table`
     (idempotent — eerste run maakt entry, volgende runs no-op)
  7. Verplaats CSV naar processed/ prefix

Requirede env-vars (gezet door csv_ingest_factory):
  SOURCE_NAME       — naam van de bron (matcht <name>.yml)
  OBJECT_KEY        — s3-key binnen staging-bucket (uit dag_run.conf)
  S3_ENDPOINT           — bv. http://minio.odap-platform.svc.cluster.local:9000
  S3_ACCESS_KEY / S3_SECRET_KEY
  TRINO_HOST / TRINO_PORT / TRINO_USER / TRINO_PASSWORD
  SOURCES_DIR       — default /opt/odap/airflow/sources

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""
from __future__ import annotations

import io
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.compute as pc
import yaml
from deltalake import DeltaTable, write_deltalake
from trino.dbapi import connect as trino_connect


# ---------------------------------------------------------------------------
# Config — uit env, geen defaults voor secrets.
# ---------------------------------------------------------------------------
SOURCE_NAME = os.environ["SOURCE_NAME"]
OBJECT_KEY = os.environ["OBJECT_KEY"]
SOURCES_DIR = Path(os.environ.get("SOURCES_DIR", "/opt/odap/airflow/sources"))

S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_REGION = os.environ.get("S3_REGION", "eu-nl-1")
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "odap-bronze")

TRINO_HOST = os.environ["TRINO_HOST"]
TRINO_PORT = int(os.environ.get("TRINO_PORT", "8443"))
TRINO_USER = os.environ["TRINO_USER"]
TRINO_PASSWORD = os.environ.get("TRINO_PASSWORD") or None
TRINO_HTTP_SCHEME = os.environ.get("TRINO_HTTP_SCHEME", "https")
TRINO_VERIFY = os.environ.get("TRINO_VERIFY", "/etc/platform-ca/ca.crt")


# ---------------------------------------------------------------------------
# Type-mapping CSV-schema → pyarrow + Trino.
#
# `decimal` en `timestamp` zijn niet in de simpele map opgenomen omdat ze
# parameters dragen (precision/scale resp. unit/tz). Voor die types valt
# `pa_type_for_column` terug op een dynamische constructie. UC-12 (FOCUS
# billing) was de eerste bron die deze types nodig had.
# ---------------------------------------------------------------------------
PA_TYPE = {
    "varchar": pa.string(),
    "integer": pa.int64(),
    "double":  pa.float64(),
    "boolean": pa.bool_(),
    "date":    pa.date32(),
}
TRINO_TYPE = {
    "varchar": "VARCHAR",
    "integer": "BIGINT",
    "double":  "DOUBLE",
    "boolean": "BOOLEAN",
    "date":    "DATE",
}
# Types waar numerieke min/max-validatie zinvol op is.
NUMERIC_TYPES = ("integer", "double", "decimal")


def pa_type_for_column(col: dict) -> pa.DataType:
    """Bepaal pyarrow-type voor één kolom-spec.

    Eenvoudige types via PA_TYPE; parameterized types (decimal, timestamp)
    krijgen een eigen tak met defaults die voor FOCUS-achtige bronnen
    werken maar in YAML overschreven kunnen worden.
    """
    t = col["type"]
    if t == "decimal":
        precision = int(col.get("precision", 18))
        scale = int(col.get("scale", 6))
        return pa.decimal128(precision, scale)
    if t == "timestamp":
        # FOCUS-export gebruikt ISO 8601 met optionele "Z"-suffix. Pyarrow's
        # CSV-converter weigert die suffix wanneer target-type tz-aware is
        # ("CSV conversion error to timestamp[us, tz=UTC]: invalid value
        # '2026-02-01T00:00:00Z'"). Daarom laden we als naive timestamp;
        # silver-model voegt de UTC-context toe (alle FOCUS-data is in UTC).
        # Microseconde-precisie matcht Trino's default timestamp(6).
        return pa.timestamp("us")
    if t not in PA_TYPE:
        sys.exit(f"ERROR: onbekend kolom-type {t!r} voor kolom {col.get('name')!r}")
    return PA_TYPE[t]


def log(msg: str) -> None:
    print(f"[csv_to_bronze] {msg}", flush=True)


def load_source_spec(name: str) -> dict:
    path = SOURCES_DIR / f"{name}.yml"
    if not path.exists():
        sys.exit(f"ERROR: source-YAML niet gevonden: {path}")
    with path.open(encoding="utf-8") as fp:
        spec = yaml.safe_load(fp)
    if spec.get("sla", {}).get("mode") != "csv_batch":
        sys.exit(f"ERROR: bron {name!r} is geen csv_batch (mode={spec.get('sla', {}).get('mode')!r})")
    return spec


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
    )


def download_csv(s3, bucket: str, key: str) -> bytes:
    log(f"download s3://{bucket}/{key}")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def parse_csv(data: bytes, schema_cols: list[dict], delimiter: str,
              has_header: bool, encoding: str) -> pa.Table:
    """Lees CSV met expliciete kolomnamen + types. Strict — onbekend type faalt."""
    column_names = [c["name"] for c in schema_cols]
    convert_options = pa_csv.ConvertOptions(
        column_types={c["name"]: pa_type_for_column(c) for c in schema_cols},
        strings_can_be_null=True,
        # Lege string in required-veld → null → not_null check vangt 'm hieronder.
        null_values=["", "NULL", "null", "NA"],
        # FOCUS-export levert timestamps als ISO 8601 met of zonder
        # milliseconden en met "Z" of "+00:00" tz-suffix. pyarrow probeert
        # deze patronen op volgorde; eerste match wint.
        timestamp_parsers=[
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ],
    )
    parse_options = pa_csv.ParseOptions(delimiter=delimiter)
    read_options = pa_csv.ReadOptions(
        column_names=None if has_header else column_names,
        skip_rows=0,
        encoding=encoding,
    )
    table = pa_csv.read_csv(
        io.BytesIO(data),
        read_options=read_options,
        parse_options=parse_options,
        convert_options=convert_options,
    )
    if has_header:
        # Header verwacht — verifieer dat alle gevraagde kolommen er zijn.
        missing = [c for c in column_names if c not in table.column_names]
        if missing:
            sys.exit(f"ERROR: CSV mist kolommen: {missing}. Aanwezig: {table.column_names}")
        # Selecteer in de gewenste volgorde (extra kolommen worden genegeerd).
        table = table.select(column_names)
    return table


def validate_constraints(table: pa.Table, schema_cols: list[dict]) -> None:
    """Check required + min/max on the pyarrow-tabel; faal hard bij overtreding."""
    n_rows = table.num_rows
    if n_rows == 0:
        sys.exit("ERROR: CSV bevat geen data-rijen")

    for col in schema_cols:
        name = col["name"]
        arr = table.column(name)
        if col.get("required", True):
            n_null = arr.null_count
            if n_null > 0:
                sys.exit(f"ERROR: kolom {name!r} required maar bevat {n_null} null-waarden")
        if col.get("min") is not None and col["type"] in NUMERIC_TYPES:
            below = pc.sum(pc.less(arr, col["min"])).as_py() or 0
            if below:
                sys.exit(f"ERROR: kolom {name!r} heeft {below} waarden < {col['min']}")
        if col.get("max") is not None and col["type"] in NUMERIC_TYPES:
            above = pc.sum(pc.greater(arr, col["max"])).as_py() or 0
            if above:
                sys.exit(f"ERROR: kolom {name!r} heeft {above} waarden > {col['max']}")


def add_metadata_columns(table: pa.Table, source_file: str,
                         partition_col: str) -> pa.Table:
    """Voeg ingestion_ts, source_file en event_date (= partitiekolom) toe."""
    n = table.num_rows
    now = datetime.now(timezone.utc)
    today = now.date()

    table = table.append_column(
        "ingestion_ts",
        pa.array([now] * n, type=pa.timestamp("us", tz="UTC")),
    )
    table = table.append_column(
        "source_file", pa.array([source_file] * n, type=pa.string())
    )
    # event_date = vandaag (load-datum). Voor backfills mag de DAG-trigger
    # later een explicit conf-veld toevoegen; voor MVP volstaat upload-dag.
    if partition_col not in table.column_names:
        table = table.append_column(
            partition_col, pa.array([today] * n, type=pa.date32())
        )
    return table


def write_to_bronze(table: pa.Table, bronze_table: str, partition_col: str) -> tuple[str, str]:
    """Append naar Delta. Pad: s3a://odap-bronze/demo/<table>/.

    Returns (write_location_s3, register_location_s3a). De S3-bucket is
    fysiek hetzelfde — alleen de URL-scheme verschilt tussen deltalake-rs
    (s3://) en Hive Metastore (s3a://, want Trino+HMS gebruikt Hadoop S3A
    FileSystem; 's3' scheme is daar niet geregistreerd).
    """
    write_location = f"s3://{BRONZE_BUCKET}/demo/{bronze_table}"
    register_location = f"s3a://{BRONZE_BUCKET}/demo/{bronze_table}"
    storage_options = {
        "AWS_ENDPOINT_URL": S3_ENDPOINT,
        "AWS_ACCESS_KEY_ID": S3_ACCESS_KEY,
        "AWS_SECRET_ACCESS_KEY": S3_SECRET_KEY,
        "AWS_REGION": S3_REGION,
        "AWS_ALLOW_HTTP": "true" if S3_ENDPOINT.startswith("http://") else "false",
        # MinIO is een single endpoint; deltalake's S3 client wil deze flag
        # om met conditional-writes om te gaan (DynamoDB lock niet aanwezig).
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }
    log(f"write_deltalake → {write_location} (rows={table.num_rows}, partition={partition_col})")
    write_deltalake(
        write_location,
        table,
        mode="append",
        partition_by=[partition_col],
        storage_options=storage_options,
    )
    return write_location, register_location


def ensure_trino_table(spec: dict, location: str) -> None:
    """Eerste run: registreer Delta-tabel in HMS via Trino. Daarna no-op."""
    bronze = spec["bronze"]
    fqn = f"{bronze['catalog']}.{bronze['schema']}.{bronze['table']}"
    log(f"register tabel in Trino: {fqn}")

    # Geen BasicAuth — de platform cluster heeft `authentication: []`, dus Trino
    # weigert password-auth ("Password not allowed for insecure authentication"
    # i.c.m. http-server.process-forwarded=true). Alleen X-Trino-User header
    # werkt; OPA doet authz. Zie ook dbt/profiles.yml.template (method=none).
    conn_kwargs = dict(
        host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER,
        http_scheme=TRINO_HTTP_SCHEME, verify=TRINO_VERIFY,
    )

    with trino_connect(**conn_kwargs) as conn:
        cur = conn.cursor()
        # Bestaat de tabel al? Dan klaar.
        cur.execute(
            f"SELECT count(*) FROM {bronze['catalog']}.information_schema.tables "
            f"WHERE table_schema = '{bronze['schema']}' "
            f"AND table_name = '{bronze['table']}'"
        )
        exists = cur.fetchone()[0] > 0
        if exists:
            log(f"  tabel {fqn} bestaat al — skip register_table")
            return

        # Schema + tabel pas registreren als deze er nog niet is.
        cur.execute(
            f"CREATE SCHEMA IF NOT EXISTS {bronze['catalog']}.{bronze['schema']}"
        )
        # Delta-connector procedure: schrijft entry naar HMS pointing naar bestaand _delta_log.
        cur.execute(
            f"CALL {bronze['catalog']}.system.register_table("
            f"schema_name => '{bronze['schema']}', "
            f"table_name => '{bronze['table']}', "
            f"table_location => '{location}'"
            f")"
        )
        cur.fetchall()
        log(f"  geregistreerd: {fqn} → {location}")


def move_to_processed(s3, bucket: str, key: str, processed_prefix: str) -> str:
    """Verplaats CSV naar processed/ — voorkomt dubbele ingest bij re-trigger."""
    filename = key.rsplit("/", 1)[-1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    new_key = f"{processed_prefix.rstrip('/')}/{stamp}_{uuid.uuid4().hex[:8]}_{filename}"
    log(f"move s3://{bucket}/{key} → s3://{bucket}/{new_key}")
    s3.copy_object(
        Bucket=bucket, Key=new_key,
        CopySource={"Bucket": bucket, "Key": key},
    )
    s3.delete_object(Bucket=bucket, Key=key)
    return new_key


def main() -> int:
    spec = load_source_spec(SOURCE_NAME)
    ingest = spec["ingest"]
    bronze = spec["bronze"]

    if ingest.get("kind") != "csv":
        sys.exit(f"ERROR: ingest.kind = {ingest.get('kind')!r}, verwacht 'csv'")

    staging = ingest["staging"]
    csv_cfg = ingest.get("csv", {})
    schema_cols = ingest["schema"]

    # Veiligheid: object_key moet binnen het verwachte prefix vallen, anders
    # kan een trigger met willekeurig pad een verkeerde CSV inladen.
    expected_prefix = staging["prefix"].rstrip("/") + "/"
    if not OBJECT_KEY.startswith(expected_prefix):
        sys.exit(
            f"ERROR: object_key {OBJECT_KEY!r} valt niet onder prefix "
            f"{expected_prefix!r} voor bron {SOURCE_NAME}"
        )

    s3 = s3_client()
    raw = download_csv(s3, staging["bucket"], OBJECT_KEY)

    table = parse_csv(
        raw, schema_cols,
        delimiter=csv_cfg.get("delimiter", ","),
        has_header=bool(csv_cfg.get("has_header", True)),
        encoding=csv_cfg.get("encoding", "utf-8"),
    )
    log(f"parsed {table.num_rows} rijen × {table.num_columns} kolommen")

    validate_constraints(table, schema_cols)

    table = add_metadata_columns(
        table,
        source_file=OBJECT_KEY,
        partition_col=bronze["partition_by"],
    )

    _, register_location = write_to_bronze(table, bronze["table"], bronze["partition_by"])
    ensure_trino_table(spec, register_location)
    move_to_processed(s3, staging["bucket"], OBJECT_KEY, staging["processed_prefix"])

    log(f"DONE — {table.num_rows} rijen in {bronze['catalog']}.{bronze['schema']}.{bronze['table']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
