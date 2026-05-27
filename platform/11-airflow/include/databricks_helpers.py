"""Databricks REST helpers — gedeeld through the uc11_databricks DAG.

Auth via Personal Access Token (DATABRICKS_TOKEN). Geen externe
Airflow-provider nodig: we praten direct with the Jobs API 2.1 en de
SQL Statements API 2.0. Stackable Airflow image (Python 3.9) blijft
ongewijzigd.

Wat we hier dekken:
  - run_job()        — POST /api/2.1/jobs/run-now, returnt run_id
  - wait_for_run()   — poll runs/get tot terminal state
  - execute_sql()    — synchrone SQL via Statement Execution API
  - request()        — laagje boven urllib voor ad-hoc REST-calls
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
# In-cluster komen deze uit Kubernetes Secret 'uc11-multiplatform-creds'.
# Lokaal: secrets/local/uc11-multiplatform.env.
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "").replace("https://", "").rstrip("/")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")
DATABRICKS_HTTP_PATH = os.environ.get("DATABRICKS_HTTP_PATH", "")
DATABRICKS_WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
DATABRICKS_CATALOG = os.environ.get("DATABRICKS_CATALOG", "databricks")


def _check_creds() -> None:
    if not (DATABRICKS_HOST and DATABRICKS_TOKEN):
        raise RuntimeError(
            "Databricks creds ontbreken: zet DATABRICKS_HOST en DATABRICKS_TOKEN."
        )


def request(
    method: str,
    path: str,
    body: dict | None = None,
) -> tuple[int, Any]:
    """HTTP-call met JSON body; returnt (status, parsed-body)."""
    _check_creds()
    url = f"https://{DATABRICKS_HOST}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {DATABRICKS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, (json.loads(text) if text else {})
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8")
        try:
            payload = json.loads(text)
        except Exception:
            payload = {"raw": text}
        return e.code, payload


# ─── Jobs API 2.1 ────────────────────────────────────────────────────
def run_job(job_id: int, params: dict | None = None) -> int:
    """Trigger run-now; returnt run_id.

    `params` wordt als notebook_params doorgegeven (string-only volgens API).
    Voor een python-wheel task moet je `python_params` gebruiken — pas dan
    deze helper aan of bouw een variant.
    """
    payload: dict[str, Any] = {"job_id": job_id}
    if params:
        payload["notebook_params"] = {k: str(v) for k, v in params.items()}
    status, body = request("POST", "/api/2.1/jobs/run-now", payload)
    if status != 200:
        raise RuntimeError(f"jobs/run-now {status}: {body}")
    return body["run_id"]


def wait_for_run(
    run_id: int,
    timeout_s: int = 3600,
    poll_interval_s: int = 20,
) -> dict:
    """Poll runs/get tot life_cycle_state terminal is. Faalt bij niet-SUCCESS."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status, body = request("GET", f"/api/2.1/jobs/runs/get?run_id={run_id}")
        if status != 200:
            raise RuntimeError(f"runs/get {status}: {body}")
        state = body.get("state", {})
        life = state.get("life_cycle_state")
        if life in ("TERMINATED", "INTERNAL_ERROR", "SKIPPED"):
            result = state.get("result_state")
            if result == "SUCCESS":
                return body
            raise RuntimeError(
                f"run {run_id} eindigde life={life} result={result}: {state}"
            )
        time.sleep(poll_interval_s)
    raise TimeoutError(f"run {run_id} niet klaar binnen {timeout_s}s")


# ─── SQL Statement Execution API 2.0 ─────────────────────────────────
def execute_sql(
    statement: str,
    warehouse_id: str | None = None,
    catalog: str | None = None,
    timeout_s: int = 120,
) -> dict:
    """Synchroon SQL tegen een SQL warehouse. Returnt full result payload."""
    wid = warehouse_id or DATABRICKS_WAREHOUSE_ID
    if not wid:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID ontbreekt.")
    body: dict[str, Any] = {
        "statement": statement,
        "warehouse_id": wid,
        # Max wait_timeout volgens API = 50s; daarna polleren we zelf.
        "wait_timeout": f"{min(timeout_s, 50)}s",
    }
    if catalog or DATABRICKS_CATALOG:
        body["catalog"] = catalog or DATABRICKS_CATALOG

    status, payload = request("POST", "/api/2.0/sql/statements", body)
    if status != 200:
        raise RuntimeError(f"sql/statements POST {status}: {payload}")

    state = payload.get("status", {}).get("state")
    sid = payload.get("statement_id")
    deadline = time.time() + timeout_s
    while state in ("PENDING", "RUNNING"):
        if time.time() > deadline:
            raise TimeoutError(f"sql statement {sid} timed out in state={state}")
        time.sleep(2)
        status, payload = request("GET", f"/api/2.0/sql/statements/{sid}")
        state = payload.get("status", {}).get("state")
    if state != "SUCCEEDED":
        raise RuntimeError(f"sql state={state}: {payload}")
    return payload
