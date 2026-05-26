"""Portal-side Airflow trigger bridge.

FastAPI sidecar in the portal pod. Exposes a single endpoint that the
browser hits to trigger `convert_to_delta` DAG runs after a file has
been uploaded to MinIO.

Endpoint
--------
POST /api/airflow/trigger-convert
    body: {
      "object_key":     "uploads/<sanitized-email>/<ts>/<file>",
      "source_format":  "csv" | "tsv" | "json" | "ndjson" | "parquet",
      "target_catalog": "bronze" | "sandbox",   # default: bronze
      "target_schema":  "<snake_case identifier>",
      "target_table":   "<snake_case identifier>",
      "partition_col":  "<column-name>" | null,
    }
    headers: X-Auth-Request-Email (set by oauth2-proxy)

    → 200 {"dag_run_id": "...", "airflow_url": "..."}
    → 400 / 401 / 403 / 502

The portal nginx is configured to proxy /api/airflow/* to 127.0.0.1:8089
and to forward the X-Auth-Request-* identity headers from oauth2-proxy.

Security
--------
- Bot creds (`airflow-api-bot` Secret) are mounted as env vars and never
  leave the pod.
- The caller's email (from oauth2-proxy) must match the `<email>` segment
  of `object_key` — prevents triggering a conversion on someone else's
  upload.
- `target_schema` and `target_table` are validated against a strict
  snake_case regex.
- DAG ID is hardcoded — no caller-supplied DAG.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger("airflow-bridge")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="UWV portal Airflow bridge", version="0.1.0")

AIRFLOW_BASE_URL = os.environ.get(
    "AIRFLOW_BASE_URL",
    "http://airflow-webserver.odap-platform.svc.cluster.local:8080",
)
AIRFLOW_USERNAME = os.environ.get("AIRFLOW_USERNAME", "")
AIRFLOW_PASSWORD = os.environ.get("AIRFLOW_PASSWORD", "")

# Externally-visible Airflow URL for the deeplink we return to the browser.
# The portal embed mounts Airflow at platform.<host>/airflow.
AIRFLOW_PUBLIC_URL = os.environ.get(
    "AIRFLOW_PUBLIC_URL",
    "https://platform.odap.local:8443/airflow",
)

CONVERT_DAG_ID = "convert_to_delta"

IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")

# Sanitisation moet overeenkomen met portal/src/pages/csv-upload.astro.
# Lowercased, '@' → '_at_', '.' → '_'. Andere ASCII-letters/digits behouden;
# alles anders wordt '_'.
_SAFE_EMAIL_CHARS = re.compile(r"[^a-z0-9_]")


def sanitize_email(email: str) -> str:
    s = email.strip().lower().replace("@", "_at_").replace(".", "_")
    return _SAFE_EMAIL_CHARS.sub("_", s)


class TriggerReq(BaseModel):
    object_key: str = Field(..., min_length=10, max_length=1024)
    source_format: Literal["csv", "tsv", "json", "ndjson", "parquet"]
    target_catalog: Literal["bronze", "sandbox"] = "bronze"
    target_schema: str = Field(..., min_length=1, max_length=63)
    target_table: str = Field(..., min_length=1, max_length=63)
    partition_col: Optional[str] = Field(default=None, max_length=63)


def _email_from_request(req: Request) -> str:
    """oauth2-proxy sets X-Auth-Request-Email when `set_xauthrequest=true`.

    Without it we fail closed — no anonymous DAG triggers.
    """
    email = req.headers.get("x-auth-request-email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="not authenticated (no email)")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="invalid email header")
    return email


def _validate_identifier(name: str, kind: str) -> None:
    if not IDENTIFIER_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail=f"invalid {kind}: must match {IDENTIFIER_RE.pattern}",
        )


def _airflow_auth_header() -> str:
    if not AIRFLOW_USERNAME or not AIRFLOW_PASSWORD:
        raise HTTPException(status_code=503, detail="airflow bot creds not configured")
    creds = base64.b64encode(f"{AIRFLOW_USERNAME}:{AIRFLOW_PASSWORD}".encode()).decode()
    return f"Basic {creds}"


def _trigger_dag(payload: dict) -> dict:
    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/{CONVERT_DAG_ID}/dagRuns"
    body = json.dumps({"conf": payload}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": _airflow_auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data
    except urllib.error.HTTPError as e:
        body_str = e.read().decode("utf-8", errors="replace")[:400]
        log.warning("airflow rejected trigger: %s — %s", e.code, body_str)
        raise HTTPException(
            status_code=502,
            detail=f"airflow rejected trigger ({e.code}): {body_str}",
        )
    except urllib.error.URLError as e:
        log.warning("airflow unreachable: %s", e)
        raise HTTPException(status_code=502, detail=f"airflow unreachable: {e.reason}")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/airflow/trigger-convert")
def trigger_convert(body: TriggerReq, request: Request) -> dict:
    email = _email_from_request(request)
    sanitized = sanitize_email(email)

    # Path-prefix check: the file must live under the caller's own uploads/<email>/
    # subtree. Prevents one user from triggering conversion of another's upload.
    expected_prefix = f"uploads/{sanitized}/"
    if not body.object_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=403,
            detail=f"object_key must start with {expected_prefix} (got {body.object_key[:80]!r})",
        )
    if ".." in body.object_key or "//" in body.object_key:
        raise HTTPException(status_code=400, detail="invalid object_key (path traversal)")

    _validate_identifier(body.target_schema, "target_schema")
    _validate_identifier(body.target_table, "target_table")
    if body.partition_col is not None:
        _validate_identifier(body.partition_col, "partition_col")

    conf = {
        "object_key":     body.object_key,
        "source_format":  body.source_format,
        "target_catalog": body.target_catalog,
        "target_schema":  body.target_schema,
        "target_table":   body.target_table,
        "partition_col":  body.partition_col,
        "source_email":   email,
    }
    log.info("triggering convert_to_delta: %s", conf)
    result = _trigger_dag(conf)
    dag_run_id = result.get("dag_run_id") or result.get("dagRunId") or ""
    return {
        "dag_run_id":  dag_run_id,
        "airflow_url": f"{AIRFLOW_PUBLIC_URL}/dags/{CONVERT_DAG_ID}/grid"
                       + (f"?dag_run_id={dag_run_id}" if dag_run_id else ""),
    }
