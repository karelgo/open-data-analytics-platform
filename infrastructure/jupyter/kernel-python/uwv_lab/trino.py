"""Pre-configured Trino client for the ODAP Lab notebook image.

Uses the trino-python-client. The X-Trino-User header is set to the Keycloak
``preferred_username`` (injected by the JupyterHub spawner as ``TRINO_USER``);
OPA receives that identity and applies the row filters, column masks and
purpose-binding rules associated with the user's realm roles.

For the dev cluster Trino runs with ``authentication: []`` so no password is
required; production overlays add Bearer-token auth and this module honors
``TRINO_PASSWORD`` if set.
"""
from __future__ import annotations

import os
from typing import Any

# Lazy imports so `import odap_lab` doesn't pull pandas/trino on every kernel.
_DEFAULTS = {
    "host": "trino-coordinator.odap-platform.svc.cluster.local",
    "port": 8443,
    "scheme": "https",
    "user": "lab-user",
    "catalog": "silver",
    "schema": "default",
}


def _conf(**overrides: Any) -> dict[str, Any]:
    return {
        "host": overrides.get("host") or os.environ.get("TRINO_HOST") or _DEFAULTS["host"],
        "port": int(overrides.get("port") or os.environ.get("TRINO_PORT") or _DEFAULTS["port"]),
        "scheme": overrides.get("scheme") or os.environ.get("TRINO_SCHEME") or _DEFAULTS["scheme"],
        "user": overrides.get("user") or os.environ.get("TRINO_USER") or _DEFAULTS["user"],
        "catalog": overrides.get("catalog") or os.environ.get("TRINO_CATALOG") or _DEFAULTS["catalog"],
        "schema": overrides.get("schema") or _DEFAULTS["schema"],
    }


def connect(**overrides: Any):
    """Return a trino.dbapi.Connection ready to use.

    Notebook idiom::

        with trino.connect() as cx:
            cur = cx.cursor()
            cur.execute("SHOW CATALOGS")
            print(cur.fetchall())
    """
    from trino.dbapi import connect as _connect

    c = _conf(**overrides)
    password = os.environ.get("TRINO_PASSWORD")
    auth = None
    if password:
        from trino.auth import BasicAuthentication

        auth = BasicAuthentication(c["user"], password)
    return _connect(
        host=c["host"],
        port=c["port"],
        user=c["user"],
        catalog=c["catalog"],
        schema=c["schema"],
        http_scheme=c["scheme"],
        auth=auth,
        # In-cluster TLS is signed by the Platform CA bundle if mounted, otherwise
        # accept self-signed (dev cluster only).
        verify=os.environ.get("CA_BUNDLE") or False,
    )


def query(sql: str, **overrides: Any):
    """Execute *sql* and return a pandas DataFrame.

    This is the convenience entrypoint most notebooks will reach for. It opens
    a fresh connection per call so the spawner-supplied identity (and any
    notebook-level overrides) is always re-evaluated.
    """
    import pandas as pd

    with connect(**overrides) as cx:
        cur = cx.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=columns)


def sqlalchemy_engine(**overrides: Any):
    """Return a SQLAlchemy engine for ``pd.read_sql`` / ``df.to_sql`` ergonomics."""
    from sqlalchemy import create_engine

    c = _conf(**overrides)
    return create_engine(
        f"trino://{c['user']}@{c['host']}:{c['port']}/{c['catalog']}/{c['schema']}",
        connect_args={"http_scheme": c["scheme"]},
    )
