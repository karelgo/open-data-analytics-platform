#!/usr/bin/env python3
"""Upload de actieve uc11 Fabric-notebooks to the workspace.

Idempotent: detecteert bestaande notebooks by displayName en doet dan een
updateDefinition (POST .../items/<id>/updateDefinition). Bij eerste run
maakt hij ze aan via POST .../notebooks.

Verwijdert ook notebooks in DEPRECATED_NOTEBOOKS from the workspace zodat
oude notebooks niet meer per ongeluk getriggered kunnen worden (bv.
uc11_dbt_gold is vervangen through the fabric_dbt_gold KPO-task die
dbt-fabricspark draait — zie uc11_fabric DAG).

Gebruik:
    set -a; source secrets/local/uc11-multiplatform.env; set +a
    python3 scripts/fabric-upload-notebooks.py

Geen externe deps; gebruikt fabric_helpers uit platform/11-airflow/include.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

# Voeg include/ toe aan PYTHONPATH zodat fabric_helpers importeert.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "platform" / "11-airflow" / "include"))

from fabric_helpers import (  # noqa: E402
    FABRIC_ENDPOINT,
    FABRIC_WORKSPACE_ID,
    get_token,
    list_items,
    request,
    wait_for_operation,
)

NOTEBOOKS_DIR = REPO_ROOT / "platform" / "11-airflow" / "fabric-notebooks"
NOTEBOOK_FILES = {
    "uc11_seed_bronze": NOTEBOOKS_DIR / "uc11_seed_bronze.ipynb",
    "uc11_silver": NOTEBOOKS_DIR / "uc11_silver.ipynb",
}

# Notebooks die ooit bestonden maar nu vervangen zijn. Worden bij elke
# upload-run gewist from the workspace — idempotent, no-op als ze er al niet zijn.
DEPRECATED_NOTEBOOKS = ("uc11_dbt_gold",)


def _payload(file: Path) -> dict:
    """Bouw een definition-payload for the Fabric REST API."""
    encoded = base64.b64encode(file.read_bytes()).decode("ascii")
    return {
        "definition": {
            "format": "ipynb",
            "parts": [
                {
                    "path": "notebook-content.ipynb",
                    "payload": encoded,
                    "payloadType": "InlineBase64",
                }
            ],
        }
    }


def create_notebook(token: str, name: str, file: Path) -> str:
    url = f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}/notebooks"
    body = {"displayName": name, **_payload(file)}
    status, headers, payload = request("POST", url, token, body)
    if status in (200, 201):
        return payload["id"]
    if status == 202:
        # long-running create; Location header heeft operation-URL
        op = headers.get("Location") or headers.get("location")
        if not op:
            raise RuntimeError(f"create_notebook 202 zonder Location: {payload}")
        wait_for_operation(token, op)
        # We weten het id niet from the operation-response — herquery items.
        for it in list_items(token, "Notebook"):
            if it["displayName"] == name:
                return it["id"]
        raise RuntimeError(f"create_notebook: na operation geen item met name {name}")
    raise RuntimeError(f"create_notebook {status}: {payload}")


def update_notebook(token: str, item_id: str, file: Path) -> None:
    url = (
        f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}"
        f"/notebooks/{item_id}/updateDefinition"
    )
    status, headers, payload = request("POST", url, token, _payload(file))
    if status in (200, 204):
        return
    if status == 202:
        op = headers.get("Location") or headers.get("location")
        if not op:
            raise RuntimeError(f"update_notebook 202 zonder Location: {payload}")
        wait_for_operation(token, op)
        return
    raise RuntimeError(f"update_notebook {status}: {payload}")


def delete_notebook(token: str, item_id: str, name: str) -> None:
    """DELETE een workspace-item. Async (202) wachten tot operation klaar is."""
    url = f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}/items/{item_id}"
    status, headers, payload = request("DELETE", url, token)
    if status in (200, 204):
        return
    if status == 202:
        op = headers.get("Location") or headers.get("location")
        if op:
            wait_for_operation(token, op)
            return
    raise RuntimeError(f"delete_notebook {name} {status}: {payload}")


def main() -> None:
    # Sanity: zijn alle actieve notebook-bestanden er?
    missing = [name for name, p in NOTEBOOK_FILES.items() if not p.exists()]
    if missing:
        print(f"FOUT: ontbrekende notebook-bestanden: {missing}", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("FABRIC_TENANT_ID"):
        print(
            "FOUT: zet eerst de env-vars met `set -a; source "
            "secrets/local/uc11-multiplatform.env; set +a`",
            file=sys.stderr,
        )
        sys.exit(2)

    token = get_token()
    existing = {n["displayName"]: n["id"] for n in list_items(token, "Notebook")}

    # 1. Upload / update actieve notebooks.
    for name, file in NOTEBOOK_FILES.items():
        if name in existing:
            print(f"UPDATE  {name:20s} (id {existing[name]}) ← {file.name}")
            update_notebook(token, existing[name], file)
        else:
            print(f"CREATE  {name:20s}                                     ← {file.name}")
            new_id = create_notebook(token, name, file)
            print(f"        → id {new_id}")

    # 2. Cleanup deprecated notebooks.
    for name in DEPRECATED_NOTEBOOKS:
        if name in existing:
            print(f"DELETE  {name:20s} (id {existing[name]}) — deprecated, vervangen door dbt-fabricspark")
            delete_notebook(token, existing[name], name)

    print()
    print("Final state:")
    for it in list_items(token, "Notebook"):
        print(f"  - {it['displayName']:20s}  {it['id']}")


if __name__ == "__main__":
    main()
