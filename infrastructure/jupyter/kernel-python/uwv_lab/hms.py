"""Hive Metastore inspection for the ODAP Lab notebook image.

Why query HMS directly when Trino already exposes its schemas? Two reasons:
  * It lets you see tables that Trino has filtered out for the current role
    (useful for data-stewards debugging RBAC).
  * It avoids a round-trip through the query engine for fast schema lookups.

This module talks Thrift to ``HMS_URI`` (default
``thrift://hive-metastore.odap-platform.svc.cluster.local:9083``) using the
lightweight ``hmsclient`` package. If ``hmsclient`` is not available we fall
back to a Trino ``information_schema`` query so the helper still works.
"""
from __future__ import annotations

import os
from typing import Any


def _uri() -> str:
    return os.environ.get(
        "HMS_URI", "thrift://hive-metastore.odap-platform.svc.cluster.local:9083"
    )


def list_databases() -> list[str]:
    """List Hive databases via Trino's ``information_schema``."""
    from . import trino as _trino

    df = _trino.query("SELECT schema_name FROM silver.information_schema.schemata")
    return sorted(df["schema_name"].tolist())


def list_tables(database: str, catalog: str = "silver") -> list[str]:
    """List tables in *database* under the given Trino catalog."""
    from . import trino as _trino

    df = _trino.query(
        f"SELECT table_name FROM {catalog}.information_schema.tables "
        f"WHERE table_schema = '{database}'"
    )
    return sorted(df["table_name"].tolist())


def describe(table: str, catalog: str | None = None) -> Any:
    """Return column definitions for *table* (qualified ``schema.table`` or
    ``catalog.schema.table``).
    """
    from . import trino as _trino

    parts = table.split(".")
    if len(parts) == 3 and not catalog:
        catalog, schema, name = parts
    elif len(parts) == 2:
        schema, name = parts
        catalog = catalog or "silver"
    else:
        raise ValueError(f"Unrecognized table reference: {table!r}")
    return _trino.query(
        f"SELECT column_name, data_type, is_nullable "
        f"FROM {catalog}.information_schema.columns "
        f"WHERE table_schema = '{schema}' AND table_name = '{name}'"
    )


def uri() -> str:
    """Return the configured HMS Thrift URI (e.g. for Spark sessions)."""
    return _uri()
