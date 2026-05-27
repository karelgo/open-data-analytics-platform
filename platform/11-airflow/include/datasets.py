"""Airflow Dataset URI-conventies for the platform pipeline.

Conventie:
    bronze://demo/<table>                 # bronze.demo.<table>
    silver://<domain>/<entity>           # silver.<domain>.stg_<entity>
    gold://<usecase>/<table>             # gold.<usecase>.<table>

Eén plek voor URI-formattering — DAGs gebruiken alleen deze helpers, niet
hardcoded strings. Zie ADR-0007.
"""
from __future__ import annotations

from airflow.datasets import Dataset

from sources_loader import SourceSpec, load_all_sources, sources_for_use_case


def bronze_dataset(source: SourceSpec) -> Dataset:
    return Dataset(f"bronze://{source.bronze.schema}/{source.bronze.table}")


def silver_dataset(source: SourceSpec) -> Dataset:
    # Strip 'stg_' van de model-naam for a nettere URI.
    entity = source.silver.staging_model.removeprefix("stg_")
    return Dataset(f"silver://{source.domain}/{entity}")


def gold_dataset(use_case: str, mart_table: str) -> Dataset:
    return Dataset(f"gold://{use_case}/{mart_table}")


def silver_datasets_for_use_case(use_case: str) -> list[Dataset]:
    """Triggers for a UC = silver-datasets van alle gebruikte bronnen."""
    return [silver_dataset(s) for s in sources_for_use_case(use_case)]


def all_bronze_datasets() -> list[Dataset]:
    return [bronze_dataset(s) for s in load_all_sources()]
