#!/usr/bin/env python3
"""any-file → Delta conversie loader.

Draait in een KubernetesPodOperator (zie dags/convert_to_delta.py).

Stappen:
  1. Lees env-conf (object_key, source_format, target_*, partition_col).
  2. Veiligheidscheck: object_key MOET onder `uploads/` prefix vallen.
  3. Download bestand uit s3://odap-staging/<object_key>.
  4. Parse op basis van source_format → pyarrow.Table.
  5. Voeg ingestion_ts + source_file metadata-kolommen toe; als geen
     partition_col is opgegeven, voeg `event_date` toe en gebruik dat.
  6. Schrijf Delta naar s3a://odap-<target_catalog>/<target_schema>/<target_table>/.
  7. Registreer Delta-tabel in Hive Metastore via Trino `system.register_table`.
  8. Verplaats bron-bestand naar processed/uploads/<oorspronkelijk-pad>.

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""
from __future__ import annotations

import io
import os
import re
import sys
import uuid
from datetime import datetime, timezone

import boto3
import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.json as pa_json
import pyarrow.parquet as pa_parquet
from deltalake import write_deltalake
from trino.dbapi import connect as trino_connect


# ---------------------------------------------------------------------------
# Config — uit env (gezet door dag_run.conf via Jinja).
# ---------------------------------------------------------------------------
OBJECT_KEY     = os.environ["OBJECT_KEY"]
SOURCE_FORMAT  = os.environ["SOURCE_FORMAT"].strip().lower()
TARGET_CATALOG = os.environ.get("TARGET_CATALOG", "bronze").strip().lower()
TARGET_SCHEMA  = os.environ["TARGET_SCHEMA"].strip().lower()
TARGET_TABLE   = os.environ["TARGET_TABLE"].strip().lower()
PARTITION_COL  = os.environ.get("PARTITION_COL", "").strip()
SOURCE_EMAIL   = os.environ.get("SOURCE_EMAIL", "")

STAGING_BUCKET = os.environ.get("STAGING_BUCKET", "odap-staging")

S3_ENDPOINT   = os.environ["S3_ENDPOINT"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_REGION     = os.environ.get("S3_REGION", "eu-nl-1")

TRINO_HOST        = os.environ["TRINO_HOST"]
TRINO_PORT        = int(os.environ.get("TRINO_PORT", "8443"))
TRINO_USER        = os.environ["TRINO_USER"]
TRINO_HTTP_SCHEME = os.environ.get("TRINO_HTTP_SCHEME", "https")
TRINO_VERIFY      = os.environ.get("TRINO_VERIFY", "/etc/platform-ca/ca.crt")

ALLOWED_FORMATS = {"csv", "tsv", "json", "ndjson", "parquet"}
IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
ALLOWED_CATALOGS = {"bronze", "sandbox"}


def log(msg: str) -> None:
    print(f"[convert_to_delta] {msg}", flush=True)


def fail(msg: str) -> None:
    log(f"ERROR: {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Validatie
# ---------------------------------------------------------------------------
def validate_inputs() -> None:
    if SOURCE_FORMAT not in ALLOWED_FORMATS:
        fail(f"source_format {SOURCE_FORMAT!r} niet ondersteund (allowed: {sorted(ALLOWED_FORMATS)})")
    if TARGET_CATALOG not in ALLOWED_CATALOGS:
        fail(f"target_catalog {TARGET_CATALOG!r} niet toegestaan (allowed: {sorted(ALLOWED_CATALOGS)})")
    if not IDENTIFIER_RE.match(TARGET_SCHEMA):
        fail(f"target_schema {TARGET_SCHEMA!r} ongeldig (snake_case verwacht)")
    if not IDENTIFIER_RE.match(TARGET_TABLE):
        fail(f"target_table {TARGET_TABLE!r} ongeldig (snake_case verwacht)")
    if PARTITION_COL and not IDENTIFIER_RE.match(PARTITION_COL):
        fail(f"partition_col {PARTITION_COL!r} ongeldig (snake_case verwacht)")
    # Bescherming: alleen uploads/ — geen customer_satisfaction/focus paden.
    if not OBJECT_KEY.startswith("uploads/"):
        fail(f"object_key {OBJECT_KEY!r} valt niet onder uploads/")
    if ".." in OBJECT_KEY or "//" in OBJECT_KEY:
        fail(f"object_key {OBJECT_KEY!r} bevat path-traversal patroon")


# ---------------------------------------------------------------------------
# Lezen
# ---------------------------------------------------------------------------
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
    )


def download(s3, bucket: str, key: str) -> bytes:
    log(f"download s3://{bucket}/{key}")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def parse_table(data: bytes, fmt: str) -> pa.Table:
    """Parse de bytes naar pyarrow.Table — type-inference op pyarrow's default."""
    buf = io.BytesIO(data)
    if fmt == "csv":
        return pa_csv.read_csv(buf)
    if fmt == "tsv":
        return pa_csv.read_csv(buf, parse_options=pa_csv.ParseOptions(delimiter="\t"))
    if fmt in ("json", "ndjson"):
        # pyarrow.json verwacht line-delimited (NDJSON). Voor een single-object
        # of -array JSON wrappen we naar één regel — werkt voor flat schemas.
        if fmt == "json":
            text = data.decode("utf-8", errors="replace").strip()
            if text.startswith("["):
                # Top-level array → split per element op één regel.
                import json as _json
                items = _json.loads(text)
                buf = io.BytesIO(b"\n".join(_json.dumps(it).encode() for it in items))
            elif text.startswith("{"):
                buf = io.BytesIO(text.encode())
            else:
                fail("json bestand begint niet met '[' of '{'")
        return pa_json.read_json(buf)
    if fmt == "parquet":
        return pa_parquet.read_table(buf)
    fail(f"onbekend formaat {fmt!r}")
    raise SystemExit(1)  # unreachable; voor de type-checker


# ---------------------------------------------------------------------------
# Metadata + schrijven
# ---------------------------------------------------------------------------
def add_metadata(table: pa.Table, source_file: str, partition_col: str | None) -> tuple[pa.Table, str]:
    """Voeg ingestion_ts + source_file + (optioneel) event_date toe.

    Als geen partition_col is opgegeven, gebruiken we de toegevoegde
    `event_date`-kolom. Als de gebruiker WEL een partition_col opgaf, dan
    moet die al in de input zitten — we voegen 'm niet automatisch toe.
    """
    n = table.num_rows
    if n == 0:
        fail("input bevat geen rijen")

    now = datetime.now(timezone.utc)
    today = now.date()

    if "ingestion_ts" not in table.column_names:
        table = table.append_column(
            "ingestion_ts",
            pa.array([now] * n, type=pa.timestamp("us", tz="UTC")),
        )
    if "source_file" not in table.column_names:
        table = table.append_column("source_file", pa.array([source_file] * n, type=pa.string()))

    if partition_col:
        if partition_col not in table.column_names:
            fail(
                f"partition_col {partition_col!r} bestaat niet in input "
                f"(beschikbaar: {table.column_names})"
            )
        return table, partition_col

    # Default: event_date = vandaag, partitiekolom.
    if "event_date" not in table.column_names:
        table = table.append_column("event_date", pa.array([today] * n, type=pa.date32()))
    return table, "event_date"


def write_to_delta(table: pa.Table, partition_col: str) -> str:
    bucket = f"odap-{TARGET_CATALOG}"
    path = f"{TARGET_SCHEMA}/{TARGET_TABLE}"
    write_location    = f"s3://{bucket}/{path}"
    register_location = f"s3a://{bucket}/{path}"
    storage_options = {
        "AWS_ENDPOINT_URL":            S3_ENDPOINT,
        "AWS_ACCESS_KEY_ID":           S3_ACCESS_KEY,
        "AWS_SECRET_ACCESS_KEY":       S3_SECRET_KEY,
        "AWS_REGION":                  S3_REGION,
        "AWS_ALLOW_HTTP":              "true" if S3_ENDPOINT.startswith("http://") else "false",
        "AWS_S3_ALLOW_UNSAFE_RENAME":  "true",
    }
    log(f"write_deltalake → {write_location} (rows={table.num_rows}, partition={partition_col})")
    write_deltalake(
        write_location,
        table,
        mode="append",
        partition_by=[partition_col],
        storage_options=storage_options,
    )
    return register_location


def ensure_trino_table(register_location: str) -> str:
    fqn = f"{TARGET_CATALOG}.{TARGET_SCHEMA}.{TARGET_TABLE}"
    log(f"register tabel in Trino: {fqn} → {register_location}")
    with trino_connect(
        host=TRINO_HOST, port=TRINO_PORT, user=TRINO_USER,
        http_scheme=TRINO_HTTP_SCHEME, verify=TRINO_VERIFY,
    ) as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT count(*) FROM {TARGET_CATALOG}.information_schema.tables "
            f"WHERE table_schema = '{TARGET_SCHEMA}' AND table_name = '{TARGET_TABLE}'"
        )
        exists = cur.fetchone()[0] > 0
        if exists:
            log(f"  tabel {fqn} bestaat al — skip register_table")
            return fqn
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_CATALOG}.{TARGET_SCHEMA}")
        cur.execute(
            f"CALL {TARGET_CATALOG}.system.register_table("
            f"schema_name => '{TARGET_SCHEMA}', "
            f"table_name => '{TARGET_TABLE}', "
            f"table_location => '{register_location}'"
            ")"
        )
        cur.fetchall()
        log(f"  geregistreerd: {fqn}")
    return fqn


def move_to_processed(s3, bucket: str, key: str) -> str:
    """Verplaats bron-bestand naar processed/uploads/... om re-trigger te voorkomen."""
    filename = key.rsplit("/", 1)[-1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Behoud subpaden van de oorspronkelijke key (na "uploads/") in processed/.
    rest = key[len("uploads/"):] if key.startswith("uploads/") else key
    parent = rest.rsplit("/", 1)[0] if "/" in rest else ""
    new_key = f"processed/uploads/{parent}/{stamp}_{uuid.uuid4().hex[:8]}_{filename}".replace("//", "/")
    log(f"move s3://{bucket}/{key} → s3://{bucket}/{new_key}")
    s3.copy_object(Bucket=bucket, Key=new_key, CopySource={"Bucket": bucket, "Key": key})
    s3.delete_object(Bucket=bucket, Key=key)
    return new_key


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    log(f"start — object_key={OBJECT_KEY} fmt={SOURCE_FORMAT} target={TARGET_CATALOG}.{TARGET_SCHEMA}.{TARGET_TABLE} user={SOURCE_EMAIL!r}")
    validate_inputs()

    s3 = s3_client()
    raw = download(s3, STAGING_BUCKET, OBJECT_KEY)

    table = parse_table(raw, SOURCE_FORMAT)
    log(f"parsed {table.num_rows} rijen × {table.num_columns} kolommen")

    table, partition_col = add_metadata(
        table,
        source_file=f"s3://{STAGING_BUCKET}/{OBJECT_KEY}",
        partition_col=PARTITION_COL or None,
    )

    register_location = write_to_delta(table, partition_col)
    fqn = ensure_trino_table(register_location)
    move_to_processed(s3, STAGING_BUCKET, OBJECT_KEY)

    log(f"DONE — {table.num_rows} rijen in {fqn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
