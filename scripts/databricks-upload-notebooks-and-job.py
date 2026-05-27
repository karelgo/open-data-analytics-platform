#!/usr/bin/env python3
"""Upload uc11 notebooks naar Databricks workspace + maak een multi-task Job.

Idempotent:
  - Notebooks worden overgeschreven (overwrite=true op import)
  - Job: zoekt op naam, doet update als bestaand, anders create

Gebruik:
    set -a; source secrets/local/uc11-multiplatform.env; set +a
    python3 scripts/databricks-upload-notebooks-and-job.py

Auth via Azure AD token (geen PAT nodig).
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = REPO_ROOT / "platform" / "12-databricks" / "uc11-notebooks"

NOTEBOOKS = {
    "uc11_seed_bronze": NOTEBOOKS_DIR / "uc11_seed_bronze.ipynb",
    "uc11_silver": NOTEBOOKS_DIR / "uc11_silver.ipynb",
}

# Notebooks die ooit bestonden maar nu vervangen zijn. Worden from the workspace
# verwijderd zodat de Job ze niet meer per ongeluk kan triggeren.
# uc11_dbt_gold (Spark-SQL inline) is vervangen through the databricks_dbt_gold
# KubernetesPodOperator in uc11_databricks DAG — die draait dbt-databricks
# tegen de SQL warehouse, symmetrisch met fabric_dbt_gold.
DEPRECATED_NOTEBOOKS = ("uc11_dbt_gold",)

JOB_NAME = "uc11-pipeline"
DEFAULT_WORKSPACE_PATH = "/Workspace/Shared/uc11"


def get_token() -> str:
    """AAD token voor Databricks REST via az CLI."""
    out = subprocess.check_output([
        "az", "account", "get-access-token",
        "--resource", "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d",
        "--query", "accessToken", "-o", "tsv",
    ], text=True).strip()
    return out


def request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    host = os.environ.get("DATABRICKS_HOST", "").replace("https://", "").rstrip("/")
    if not host:
        raise RuntimeError("DATABRICKS_HOST niet gezet")
    url = f"https://{host}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text else {})
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, {"raw": text}


# ─── Workspace API ───────────────────────────────────────────────────
def ensure_directory(path: str) -> None:
    status, body = request("POST", "/api/2.0/workspace/mkdirs", {"path": path})
    if status != 200:
        raise RuntimeError(f"mkdirs {path} faalde {status}: {body}")


def import_notebook(local_path: Path, workspace_path: str) -> None:
    content_b64 = base64.b64encode(local_path.read_bytes()).decode()
    body = {
        "path": workspace_path,
        "content": content_b64,
        "format": "JUPYTER",
        "language": "PYTHON",
        "overwrite": True,
    }
    status, payload = request("POST", "/api/2.0/workspace/import", body)
    if status != 200:
        raise RuntimeError(f"import {workspace_path} faalde {status}: {payload}")


# ─── Jobs API ────────────────────────────────────────────────────────
def find_job(name: str) -> int | None:
    """Geeft job_id terug als job met deze naam bestaat, anders None."""
    status, payload = request("GET", f"/api/2.1/jobs/list?name={urllib.parse.quote(name)}")
    if status != 200:
        return None
    for j in payload.get("jobs", []):
        if j.get("settings", {}).get("name") == name:
            return j["job_id"]
    return None


def build_job_settings() -> dict:
    """Multi-task job met 2 sequentiële notebook-tasks op één shared job-cluster.

    De gold-laag draait NIET meer als notebook-task in deze Job — die is
    verplaatst to the databricks_dbt_gold KubernetesPodOperator in de
    uc11_databricks Airflow DAG (die roept dbt-databricks aan tegen de SQL
    warehouse). Symmetrisch met fabric_dbt_gold in uc11_fabric.
    """
    base_path = DEFAULT_WORKSPACE_PATH
    cluster_spec = {
        "spark_version": "15.4.x-scala2.12",
        "node_type_id": "Standard_D4ds_v4",
        "num_workers": 0,
        "data_security_mode": "SINGLE_USER",
        "spark_conf": {
            "spark.databricks.cluster.profile": "singleNode",
            "spark.master": "local[*]",
        },
        "custom_tags": {"ResourceClass": "SingleNode", "project": "uc11"},
    }
    return {
        "name": JOB_NAME,
        "tags": {"project": "uc11", "platform": "databricks"},
        "max_concurrent_runs": 1,
        "job_clusters": [{
            "job_cluster_key": "uc11-cluster",
            "new_cluster": cluster_spec,
        }],
        "tasks": [
            {
                "task_key": "seed_bronze",
                "job_cluster_key": "uc11-cluster",
                "notebook_task": {
                    "notebook_path": f"{base_path}/uc11_seed_bronze",
                    "base_parameters": {"catalog": "databricks"},
                },
                "timeout_seconds": 1800,
            },
            {
                "task_key": "silver",
                "job_cluster_key": "uc11-cluster",
                "depends_on": [{"task_key": "seed_bronze"}],
                "notebook_task": {
                    "notebook_path": f"{base_path}/uc11_silver",
                    "base_parameters": {"catalog": "databricks"},
                },
                "timeout_seconds": 1800,
            },
        ],
    }


def list_workspace_notebooks(parent_path: str) -> list[dict]:
    """Lijst notebook-items onder een Workspace-pad. Databricks Workspace List is
    een GET (anders dan import/delete die POST gebruiken)."""
    status, payload = request("GET", f"/api/2.0/workspace/list?path={urllib.parse.quote(parent_path)}")
    if status == 404:
        return []
    if status != 200:
        raise RuntimeError(f"workspace/list {parent_path} faalde {status}: {payload}")
    return [o for o in payload.get("objects", []) if o.get("object_type") == "NOTEBOOK"]


def delete_workspace_object(path: str) -> None:
    """DELETE een notebook of map from the workspace."""
    status, payload = request("POST", "/api/2.0/workspace/delete",
                              {"path": path, "recursive": False})
    if status not in (200, 204):
        raise RuntimeError(f"workspace/delete {path} faalde {status}: {payload}")


def create_or_update_job() -> int:
    settings = build_job_settings()
    existing = find_job(JOB_NAME)
    if existing:
        status, body = request("POST", "/api/2.1/jobs/reset", {
            "job_id": existing, "new_settings": settings,
        })
        if status != 200:
            raise RuntimeError(f"jobs/reset faalde {status}: {body}")
        print(f"  UPDATE job_id={existing}")
        return existing
    status, body = request("POST", "/api/2.1/jobs/create", settings)
    if status != 200:
        raise RuntimeError(f"jobs/create faalde {status}: {body}")
    print(f"  CREATE job_id={body['job_id']}")
    return body["job_id"]


def main() -> None:
    print(f"=== Notebooks uploaden naar {DEFAULT_WORKSPACE_PATH} ===")
    ensure_directory(DEFAULT_WORKSPACE_PATH)
    for name, local in NOTEBOOKS.items():
        target = f"{DEFAULT_WORKSPACE_PATH}/{name}"
        print(f"  IMPORT  {name:20s} ← {local.name}")
        import_notebook(local, target)

    # Cleanup deprecated notebooks (uc11_dbt_gold — vervangen door KPO).
    existing_notebooks = {
        Path(o["path"]).name: o["path"]
        for o in list_workspace_notebooks(DEFAULT_WORKSPACE_PATH)
    }
    for name in DEPRECATED_NOTEBOOKS:
        if name in existing_notebooks:
            print(f"  DELETE  {name:20s} — deprecated, vervangen door dbt-databricks KPO")
            delete_workspace_object(existing_notebooks[name])

    print()
    print(f"=== Job '{JOB_NAME}' opzetten ===")
    job_id = create_or_update_job()

    print()
    print("Klaar.")
    print(f"  Job URL: https://{os.environ['DATABRICKS_HOST']}/jobs/{job_id}")
    print(f"  job_id: {job_id}")
    print()
    print("Zet in Airflow:")
    print(f"  airflow variables set databricks_uc11_job_id {job_id}")
    print("  (Job heeft 2 tasks: seed_bronze + silver. Gold-laag draait via")
    print("   databricks_dbt_gold KubernetesPodOperator in uc11_databricks DAG.)")


if __name__ == "__main__":
    if not os.environ.get("DATABRICKS_HOST"):
        print("Zet DATABRICKS_HOST eerst via secrets/local/uc11-multiplatform.env", file=sys.stderr)
        sys.exit(1)
    main()
