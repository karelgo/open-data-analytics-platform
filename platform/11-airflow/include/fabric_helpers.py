"""Microsoft Fabric REST helpers — gedeeld through the uc11_fabric DAG.

Auth via Service Principal (client-credentials flow tegen Azure AD).
Geen externe Airflow-provider nodig: we praten direct with the REST API
zodat de Stackable Airflow image (Python 3.9, geen apache-airflow-providers-
microsoft-fabric) ongewijzigd blijft.

Wat we hier dekken:
  - get_token()              — OAuth2 access token (Fabric of OneLake scope)
  - list_items()             — workspace-items, optioneel gefilterd op type
  - list_lakehouse_tables()  — Delta-tabellen die de SQL endpoint heeft gesynct
  - trigger_notebook()       — start een notebook-job, returnt operation-URL
  - wait_for_operation()     — poll tot Completed/Failed/Cancelled
  - request()                — laagje boven urllib voor ad-hoc REST-calls

SQL queries tegen het SQL endpoint doen we vanuit Superset (TDS-driver
zit in de Superset-image, niet in Airflow).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# ─── Env-driven defaults ─────────────────────────────────────────────
# In-cluster komen deze uit Kubernetes Secret 'uc11-multiplatform-creds'
# (toe te voegen in platform/11-airflow/uc11-multiplatform-secret.yaml).
# Lokaal: secrets/local/uc11-multiplatform.env via `set -a; source ...`.
FABRIC_TENANT_ID = os.environ.get("FABRIC_TENANT_ID", "")
FABRIC_CLIENT_ID = os.environ.get("FABRIC_CLIENT_ID", "")
FABRIC_CLIENT_SECRET = os.environ.get("FABRIC_CLIENT_SECRET", "")
FABRIC_WORKSPACE_ID = os.environ.get("FABRIC_WORKSPACE_ID", "")
FABRIC_LAKEHOUSE_ID = os.environ.get("FABRIC_LAKEHOUSE_ID", "")
FABRIC_ENDPOINT = os.environ.get(
    "FABRIC_ENDPOINT", "https://api.fabric.microsoft.com/v1"
).rstrip("/")

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
ONELAKE_SCOPE = "https://storage.azure.com/.default"
_TOKEN_URL_TPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


# ─── Low-level HTTP ──────────────────────────────────────────────────
def get_token(scope: str = FABRIC_SCOPE) -> str:
    """OAuth2 client-credentials token. Returnt access_token-string."""
    if not (FABRIC_TENANT_ID and FABRIC_CLIENT_ID and FABRIC_CLIENT_SECRET):
        raise RuntimeError(
            "Fabric SP-creds ontbreken: zet FABRIC_TENANT_ID, "
            "FABRIC_CLIENT_ID en FABRIC_CLIENT_SECRET."
        )
    body = urllib.parse.urlencode(
        {
            "client_id": FABRIC_CLIENT_ID,
            "client_secret": FABRIC_CLIENT_SECRET,
            "scope": scope,
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _TOKEN_URL_TPL.format(tenant=FABRIC_TENANT_ID),
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]


def request(
    method: str,
    url: str,
    token: str,
    body: dict | None = None,
) -> tuple[int, dict, Any]:
    """HTTP-call met JSON body; returnt (status, headers, parsed-body)."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
            payload = json.loads(text) if text else {}
            return resp.status, dict(resp.headers), payload
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8")
        try:
            payload = json.loads(text)
        except Exception:
            payload = {"raw": text}
        return e.code, dict(e.headers), payload


# ─── Workspace / item-CRUD ───────────────────────────────────────────
def list_items(token: str, item_type: str | None = None) -> list[dict]:
    """Items in de workspace, optioneel gefilterd op type (Notebook, Lakehouse, ...)."""
    url = f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}/items"
    status, _, payload = request("GET", url, token)
    if status != 200:
        raise RuntimeError(f"list_items {status}: {payload}")
    items = payload.get("value", [])
    if item_type:
        items = [i for i in items if i.get("type") == item_type]
    return items


def list_lakehouse_tables(token: str, lakehouse_id: str | None = None) -> list[str]:
    """Delta-tabel-namen volgens de Lakehouse SQL endpoint sync.

    Belangrijk: er zit een sync-delay tussen een notebook-write en de
    tables-endpoint (vaak <60s). Callers die net schreven moeten een
    paar keer retryen.
    """
    lh = lakehouse_id or FABRIC_LAKEHOUSE_ID
    if not lh:
        raise RuntimeError("FABRIC_LAKEHOUSE_ID niet gezet.")
    url = f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}/lakehouses/{lh}/tables"
    status, _, payload = request("GET", url, token)
    if status != 200:
        raise RuntimeError(f"list_lakehouse_tables {status}: {payload}")
    return [t["name"] for t in payload.get("data", [])]


# ─── Notebook-jobs ───────────────────────────────────────────────────
def trigger_notebook(
    token: str,
    notebook_id: str,
    parameters: dict | None = None,
) -> str:
    """Start een notebook-job; returnt de Location-URL voor status-polling."""
    url = (
        f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}"
        f"/items/{notebook_id}/jobs/instances?jobType=RunNotebook"
    )
    body: dict[str, Any] = {}
    if parameters:
        # Fabric verwacht parameters in {name: {value, type}}-vorm.
        body["executionData"] = {
            "parameters": {
                k: {"value": str(v), "type": "string"} for k, v in parameters.items()
            }
        }
    status, headers, payload = request("POST", url, token, body or None)
    if status not in (200, 202):
        raise RuntimeError(f"trigger_notebook {status}: {payload}")
    location = headers.get("Location") or headers.get("location")
    if not location:
        raise RuntimeError("trigger_notebook: geen Location-header in response")
    return location


def wait_for_operation(
    token: str,
    operation_url: str,
    timeout_s: int = 1800,
    poll_interval_s: int = 15,
) -> dict:
    """Poll een long-running operation tot Completed of error-state."""
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        status, _, payload = request("GET", operation_url, token)
        last = payload
        if status == 200:
            state = (payload.get("status") or payload.get("state") or "").lower()
            if state in ("completed", "succeeded"):
                return payload
            if state in ("failed", "cancelled", "deduped"):
                raise RuntimeError(f"operation in state={state}: {payload}")
        time.sleep(poll_interval_s)
    raise TimeoutError(f"operation niet klaar binnen {timeout_s}s; laatste: {last}")
