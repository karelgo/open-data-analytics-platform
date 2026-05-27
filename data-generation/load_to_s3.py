"""Genereer + publiceer synthetische events naar S3 raw zone.

SYNTHETIC DATA — NOT FOR REAL USE.

Vervangt load_to_kafka.py: i.p.v. Kafka publishen schrijven we JSONL-bestanden
naar `s3a://odap-raw/<domain>/<entity>/dt=<YYYY-MM-DD>/part-<batch>-<ts>.jsonl`.
Eén regel per envelope. Spark Structured Streaming (file source) leest deze
directory en schrijft naar Delta-bronze. Zie
`spark-jobs/streaming_files_to_lakehouse.py`.

Voorbeeldgebruik:
  uv run python load_to_s3.py --count 10000 \\
    --bucket odap-raw --endpoint http://localhost:9000

In-cluster: zie data-generation/k8s/seed-job.yaml.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/app")

from generators import (
    crm,
    fez,
    polisadministratie,
    wajong,
    wia,
    ww,
    zw,
)
from generators import (
    persona as persona_mod,
)


def _stream_to_path(stream: str) -> str:
    """`customers.created` → `customers/created`."""
    return stream.replace(".", "/")


class _S3Writer:
    """Buffer envelopes in-memory en flush per stream als JSONL naar S3."""

    def __init__(self, s3_client, bucket: str, batch_id: str):
        self._s3 = s3_client
        self._bucket = bucket
        self._batch_id = batch_id
        self._buffers: dict[str, io.StringIO] = {}
        self._counts: dict[str, int] = {}

    def write(self, stream: str, envelope: dict[str, Any]) -> None:
        buf = self._buffers.setdefault(stream, io.StringIO())
        buf.write(json.dumps(envelope, ensure_ascii=False))
        buf.write("\n")
        self._counts[stream] = self._counts.get(stream, 0) + 1

    def flush(self, stream: str) -> int:
        buf = self._buffers.pop(stream, None)
        if buf is None:
            return 0
        body = buf.getvalue().encode("utf-8")
        if not body:
            return 0
        dt = datetime.now(UTC).strftime("%Y-%m-%d")
        ts = int(time.time())
        key = f"{_stream_to_path(stream)}/dt={dt}/" f"part-{self._batch_id}-{ts}.jsonl"
        self._s3.put_object(
            Bucket=self._bucket, Key=key, Body=body, ContentType="application/x-ndjson"
        )
        return self._counts.get(stream, 0)


class _NullWriter:
    """Dry-run: tel rijen maar schrijf niets."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def write(self, stream: str, envelope: dict[str, Any]) -> None:
        self._counts[stream] = self._counts.get(stream, 0) + 1

    def flush(self, stream: str) -> int:
        return self._counts.get(stream, 0)


def _emit(writer, stream: str, items: Iterable, to_envelope) -> int:
    started = time.monotonic()
    n = 0
    for item in items:
        writer.write(stream, to_envelope(item))
        n += 1
    written = writer.flush(stream)
    dur = time.monotonic() - started
    rate = n / dur if dur > 0 else 0
    print(f"  {stream}: {written or n} events in {dur:.1f}s ({rate:.0f}/s)", flush=True)
    return n


@click.command()
@click.option("--count", default=10000, show_default=True, help="Aantal personas (anchor count).")
@click.option("--seed", default=2026, show_default=True, help="RNG-seed.")
@click.option("--bucket", default="odap-raw", show_default=True, help="S3 bucket for the raw zone.")
@click.option(
    "--endpoint",
    envvar="S3_ENDPOINT",
    default="https://minio.odap-platform.svc.cluster.local:9000",
    show_default=True,
    help="S3 endpoint URL.",
)
@click.option(
    "--region",
    envvar="S3_REGION",
    default="us-east-1",
    show_default=True,
    help="S3 region (MinIO default = us-east-1).",
)
@click.option(
    "--insecure",
    envvar="S3_INSECURE",
    is_flag=True,
    help="TLS certificate verificatie uitschakelen (self-signed MinIO).",
)
@click.option(
    "--include-domains",
    default="persona,polisadm,ww,wia,wajong,zw,crm,fez",
    show_default=True,
    help="Comma-separated lijst van domeinen om te publiceren.",
)
@click.option("--dry-run", is_flag=True, help="Genereer maar schrijf niet naar S3.")
def main(
    count: int,
    seed: int,
    bucket: str,
    endpoint: str,
    region: str,
    insecure: bool,
    include_domains: str,
    dry_run: bool,
) -> None:
    """Genereer en publiceer synthetische events to the S3 raw zone."""
    domains = {d.strip() for d in include_domains.split(",") if d.strip()}
    batch_id = uuid.uuid4().hex[:8]

    if not dry_run:
        import boto3
        from botocore.config import Config

        access_key = os.environ.get("S3_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("S3_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        if not access_key or not secret_key:
            raise click.UsageError(
                "Required S3_ACCESS_KEY/S3_SECRET_KEY (of AWS_*) env vars voor non-dry-run."
            )
        if insecure or endpoint.startswith("https://"):
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            verify=not insecure,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        writer = _S3Writer(s3, bucket, batch_id)
    else:
        writer = _NullWriter()

    print(
        f"==> Loader start (count={count}, seed={seed}, bucket={bucket}, "
        f"batch_id={batch_id}, dry_run={dry_run})",
        flush=True,
    )

    personas = list(persona_mod.generate_personas(count, seed=seed))
    bsns = [p.bsn for p in personas]
    if "persona" in domains:
        _emit(writer, "customers.created", personas, persona_mod.to_kafka_envelope)

    if "policies" in domains:
        _emit(
            writer,
            "customers.policy",
            polisadministratie.generate_ikvs(bsns, seed=seed),
            polisadministratie.to_kafka_envelope,
        )

    if "service_requests" in domains:
        _emit(
            writer,
            "service_requests.application",
            ww.generate_ww_request(bsns, seed=seed),
            ww.to_kafka_envelope,
        )

    if "claims" in domains:
        _emit(
            writer,
            "claims.application",
            wia.generate_wia_request(bsns, seed=seed),
            wia.to_kafka_envelope,
        )

    if "eligibility_cases" in domains:
        _emit(
            writer,
            "eligibility_cases.case",
            wajong.generate_eligibility_cases(bsns, seed=seed),
            wajong.to_kafka_envelope,
        )

    if "incidents" in domains:
        _emit(
            writer,
            "incidents.report",
            zw.generate_incident_reporten(bsns, seed=seed),
            zw.to_kafka_envelope,
        )

    if "customers" in domains:
        _emit(
            writer,
            "customers.interaction",
            crm.generate_customer interactionen(bsns, seed=seed),
            crm.to_kafka_envelope,
        )

    if "finance" in domains:
        _emit(
            writer,
            "finance.expense",
            fez.generate_fez_aggregaten(seed=seed),
            fez.to_kafka_envelope,
        )

    print("==> Loader klaar.", flush=True)


if __name__ == "__main__":
    main()
