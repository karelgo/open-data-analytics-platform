"""Schrijf generator-output naar MinIO staging-bucket als JSON-Lines.

Wordt in fase 4 niet gebruikt (Kafka-pad is primair). Bestaat als
voorbereiding voor batch-ingest scenario's (NiFi GetS3 → PutKafka of
direct Spark batch reads).

SYNTHETIC DATA — NOT FOR REAL USE. STUB.
"""

from __future__ import annotations

import sys

import click


@click.command()
@click.option("--count", default=10000)
@click.option("--bucket", default="odap-staging")
@click.option("--prefix", default="incoming/persona")
def main(count: int, bucket: str, prefix: str) -> None:
    """Stub — implementeer in fase 5 als batch-ingest path nodig is."""
    click.echo(
        f"STUB: zou {count} personas naar s3://{bucket}/{prefix}/*.jsonl schrijven.\n"
        "Implementeer in fase 5+ met boto3 of minio-py."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
