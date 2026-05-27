"""YAML-source-registry loader.

Eén bron van waarheid voor alle DAG-factories. Leest YAML's uit
`SOURCES_DIR` (default `/opt/odap/airflow/sources`) en geeft typed
SourceSpec objecten terug. Zie docs/adr/0007-airflow-pipeline-architecture.md.

Twee soorten bronnen:
  - Stream/streaming (default): `stream:` blok verplicht, mode = streaming|batch.
    Producer schrijft JSONL naar s3://odap-raw/<stream-path>/dt=…, Spark
    Structured Streaming (file source) leest die en schrijft naar bronze.
  - CSV-upload (mode = csv_batch): `stream:` mag ontbreken, in plaats daarvan
    een `ingest:` blok dat staging-bucket + CSV-schema beschrijft. Wordt door
    csv_ingest_factory naar bronze geschreven via een KubernetesPodOperator.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


SOURCES_DIR_ENV = "SOURCES_DIR"
DEFAULT_SOURCES_DIR = "/opt/odap/airflow/sources"

# SLA-mode constanten — gebruikt door factories om zich anders te gedragen
# voor csv_batch bronnen (skip stream-paden, eigen ingest-DAG).
MODE_STREAMING = "streaming"
MODE_BATCH = "batch"
MODE_CSV_BATCH = "csv_batch"


@dataclass(frozen=True)
class StreamSpec:
    """Stream-identifier voor JSONL-bestanden in s3://odap-raw/<path>/.

    `name` is de logische stream (bv. 'customers.created'); de Spark-job
    leidt het S3-pad af door punten te vervangen door slashes. `key` is het
    natuurlijke partition-key voor downstream silver-modellen (geen invloed
    op file-layout).
    """
    name: str
    key: str


@dataclass(frozen=True)
class BronzeSpec:
    catalog: str
    schema: str
    table: str
    partition_by: str

    @property
    def fqn(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.table}"


@dataclass(frozen=True)
class SilverSpec:
    catalog: str
    schema: str
    staging_model: str
    dbt_tag: str

    @property
    def fqn(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.staging_model}"


@dataclass(frozen=True)
class GovernanceSpec:
    legal_basis: str
    doelbinding: tuple[str, ...]
    bio_classificatie: str
    bewaartermijn_jaren: int
    eigenaar: str
    pii_kolommen: tuple[str, ...]
    risk_tier: str


@dataclass(frozen=True)
class SLASpec:
    mode: str                              # streaming | batch | csv_batch
    expected_event_freq: str
    max_acceptable_lag_seconds: int
    alert_threshold_seconds: int


@dataclass(frozen=True)
class CsvColumnSpec:
    name: str
    type: str                              # date | varchar | integer | double | boolean
    required: bool = True
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class CsvIngestSpec:
    """CSV-upload pad — staging-locatie en schema."""
    staging_bucket: str
    staging_prefix: str
    processed_prefix: str
    delimiter: str
    has_header: bool
    encoding: str
    schema: tuple[CsvColumnSpec, ...]


@dataclass(frozen=True)
class SourceSpec:
    schema_version: int
    name: str
    domain: str
    bronze: BronzeSpec
    silver: SilverSpec
    governance: GovernanceSpec
    sla: SLASpec
    used_by_use_cases: tuple[str, ...]
    anchor: bool
    # Optioneel — afhankelijk van het pad waarmee de bron binnenkomt.
    stream: StreamSpec | None = None
    csv_ingest: CsvIngestSpec | None = None

    # Voor Airflow tags op de gegenereerde DAGs.
    @property
    def airflow_tags(self) -> list[str]:
        return [
            "demo",
            f"domain:{self.domain}",
            f"classificatie:{self.governance.bio_classificatie}",
            f"risk:{self.governance.risk_tier}",
            f"mode:{self.sla.mode}",
        ]


def _sources_dir() -> Path:
    return Path(os.environ.get(SOURCES_DIR_ENV, DEFAULT_SOURCES_DIR))


def _coerce_csv_ingest(d: dict) -> CsvIngestSpec:
    if d.get("kind") != "csv":
        raise ValueError(f"ingest.kind moet 'csv' zijn, kreeg {d.get('kind')!r}")
    staging = d["staging"]
    csv_cfg = d.get("csv", {})
    cols = tuple(
        CsvColumnSpec(
            name=c["name"],
            type=c["type"],
            required=bool(c.get("required", True)),
            min=c.get("min"),
            max=c.get("max"),
        )
        for c in d["schema"]
    )
    return CsvIngestSpec(
        staging_bucket=staging["bucket"],
        staging_prefix=staging["prefix"],
        processed_prefix=staging.get("processed_prefix", staging["prefix"] + "_processed"),
        delimiter=csv_cfg.get("delimiter", ","),
        has_header=bool(csv_cfg.get("has_header", True)),
        encoding=csv_cfg.get("encoding", "utf-8"),
        schema=cols,
    )


def _coerce(d: dict) -> SourceSpec:
    sla = SLASpec(**d["sla"])
    stream_block = d.get("stream")
    ingest_block = d.get("ingest")

    # Validatie per mode — vroeg falen i.p.v. cryptische DAG-runtime-errors.
    if sla.mode == MODE_CSV_BATCH:
        if not ingest_block:
            raise ValueError(f"{d.get('name')}: mode=csv_batch vereist `ingest:` blok")
    else:
        if not stream_block:
            raise ValueError(
                f"{d.get('name')}: mode={sla.mode!r} vereist `stream:` blok "
                "(alleen csv_batch mag stream weglaten)"
            )

    return SourceSpec(
        schema_version=int(d["schema_version"]),
        name=d["name"],
        domain=d["domain"],
        stream=StreamSpec(**stream_block) if stream_block else None,
        csv_ingest=_coerce_csv_ingest(ingest_block) if ingest_block else None,
        bronze=BronzeSpec(**d["bronze"]),
        silver=SilverSpec(**d["silver"]),
        governance=GovernanceSpec(
            legal_basis=d["governance"]["legal_basis"],
            doelbinding=tuple(d["governance"]["doelbinding"]),
            bio_classificatie=d["governance"]["bio_classificatie"],
            bewaartermijn_jaren=int(d["governance"]["bewaartermijn_jaren"]),
            eigenaar=d["governance"]["eigenaar"],
            pii_kolommen=tuple(d["governance"].get("pii_kolommen") or []),
            risk_tier=d["governance"]["risk_tier"],
        ),
        sla=sla,
        used_by_use_cases=tuple(d.get("used_by_use_cases") or []),
        anchor=bool(d.get("anchor", False)),
    )


@lru_cache(maxsize=1)
def load_all_sources() -> tuple[SourceSpec, ...]:
    """Laad alle YAML's uit SOURCES_DIR. Gecached per Airflow-parse."""
    base = _sources_dir()
    if not base.exists():
        return ()
    specs: list[SourceSpec] = []
    for path in sorted(base.glob("*.yml")):
        with path.open(encoding="utf-8") as fp:
            data = yaml.safe_load(fp)
        try:
            specs.append(_coerce(data))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid source spec in {path}: {exc}") from exc
    _validate_uniqueness(specs)
    return tuple(specs)


def get_source(name: str) -> SourceSpec:
    for spec in load_all_sources():
        if spec.name == name:
            return spec
    raise KeyError(f"Unknown source: {name}")


def sources_for_use_case(uc: str) -> tuple[SourceSpec, ...]:
    return tuple(s for s in load_all_sources() if uc in s.used_by_use_cases)


def csv_batch_sources() -> tuple[SourceSpec, ...]:
    """Bronnen met `mode: csv_batch` — voor csv_ingest_factory."""
    return tuple(s for s in load_all_sources() if s.sla.mode == MODE_CSV_BATCH)


def stream_sources() -> tuple[SourceSpec, ...]:
    """Bronnen die via stream-files (S3 raw) binnenkomen — voor bronze_watch."""
    return tuple(s for s in load_all_sources() if s.stream is not None)


def _validate_uniqueness(specs: list[SourceSpec]) -> None:
    seen_names: set[str] = set()
    seen_streams: set[str] = set()
    seen_bronze: set[str] = set()
    for s in specs:
        if s.name in seen_names:
            raise ValueError(f"Duplicate source name: {s.name}")
        if s.stream and s.stream.name in seen_streams:
            raise ValueError(f"Duplicate stream name: {s.stream.name}")
        if s.bronze.fqn in seen_bronze:
            raise ValueError(f"Duplicate bronze table: {s.bronze.fqn}")
        seen_names.add(s.name)
        if s.stream:
            seen_streams.add(s.stream.name)
        seen_bronze.add(s.bronze.fqn)
