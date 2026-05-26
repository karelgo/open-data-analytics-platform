"""ODAP Lab — one-line access to every platform data layer from a notebook.

Quick start in a notebook cell::

    from odap_lab import trino, s3, hms, om

    # SQL against the Bronze / Silver / Gold / Sensitive Trino catalogs
    # (OPA evaluates row filters and column masks for your Keycloak role).
    df = trino.query("SELECT * FROM silver.wia.aanvraag LIMIT 100")

    # Browse raw objects in MinIO.
    s3.ls("odap-bronze/")

    # Inspect the Hive Metastore catalog directly.
    hms.list_tables("uwv")

    # Hit the OpenMetadata API.
    om.tables(catalog="silver")

The helper reads env vars set by the JupyterHub spawner (see
``platform/16-jupyter/configmap-jupyterhub.yaml``):

    TRINO_HOST, TRINO_PORT, TRINO_USER, TRINO_SCHEME, TRINO_CATALOG
    S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_REGION
    HMS_URI
    KAFKA_BOOTSTRAP_SERVERS
    OPENMETADATA_HOST, OPENMETADATA_JWT
    CA_BUNDLE  (combined CA file mounted into the pod)

Everything respects the user's Keycloak identity: Trino queries set
``X-Trino-User`` to ``TRINO_USER`` (= ``preferred_username``), and OPA enforces
purpose-binding, row filters and column masking from there.
"""
from __future__ import annotations

from . import s3, trino, hms, om, kafka

__all__ = ["s3", "trino", "hms", "om", "kafka", "env"]


def env() -> dict[str, str | None]:
    """Return the connection-relevant env-vars for diagnostic notebooks."""
    import os

    keys = [
        "TRINO_HOST",
        "TRINO_PORT",
        "TRINO_USER",
        "TRINO_SCHEME",
        "TRINO_CATALOG",
        "S3_ENDPOINT",
        "S3_REGION",
        "HMS_URI",
        "KAFKA_BOOTSTRAP_SERVERS",
        "OPENMETADATA_HOST",
        "CA_BUNDLE",
    ]
    return {k: os.environ.get(k) for k in keys}
