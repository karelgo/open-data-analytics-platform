"""OpenMetadata API helpers for notebook use.

We don't import the heavy ``openmetadata-ingestion`` SDK eagerly because every
import-time it pulls a forest of pydantic models. Instead we make plain HTTPS
calls via ``requests`` against the catalog API and let users opt in to the
full SDK when they need it.
"""
from __future__ import annotations

import os
from typing import Any


def _base_url() -> str:
    # In-cluster default — the Helm-installed OM Service. Falls back to the
    # public ingress for laptop debugging when running outside the cluster.
    return os.environ.get(
        "OPENMETADATA_HOST",
        "http://openmetadata.odap-meta.svc.cluster.local:8585",
    ).rstrip("/")


def _headers() -> dict[str, str]:
    jwt = os.environ.get("OPENMETADATA_JWT", "")
    h = {"Accept": "application/json"}
    if jwt:
        h["Authorization"] = f"Bearer {jwt}"
    return h


def _verify() -> bool | str:
    bundle = os.environ.get("CA_BUNDLE")
    return bundle if bundle else False


def get(path: str, **params: Any) -> dict:
    """GET a path under ``/api/v1`` and return the JSON payload."""
    import requests

    url = f"{_base_url()}/api/v1/{path.lstrip('/')}"
    r = requests.get(url, headers=_headers(), params=params, verify=_verify(), timeout=15)
    r.raise_for_status()
    return r.json()


def tables(catalog: str | None = None, limit: int = 50) -> list[dict]:
    """List tables in OpenMetadata, optionally filtered by Trino-catalog name.

    Returns the raw entity dicts so callers can ``pd.json_normalize`` them.
    """
    params: dict[str, Any] = {"limit": limit, "fields": "tags,owner,columns"}
    if catalog:
        params["database"] = f"trino.{catalog}"
    payload = get("tables", **params)
    return payload.get("data", [])


def lineage_for(fqn: str) -> dict:
    """Return upstream + downstream lineage for a fully-qualified table name."""
    return get(f"lineage/table/name/{fqn}", upstreamDepth=3, downstreamDepth=3)


def glossary_terms(glossary: str = "glossary") -> list[dict]:
    """List terms in the given glossary."""
    payload = get(f"glossaryTerms", glossary=glossary, limit=200)
    return payload.get("data", [])


def ui_link(fqn: str) -> str:
    """Convenience: build the OpenMetadata UI URL for a table FQN."""
    public = os.environ.get(
        "OPENMETADATA_PUBLIC_URL", "https://openmetadata.odap.local:8443"
    )
    return f"{public.rstrip('/')}/table/{fqn}"
