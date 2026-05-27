#!/usr/bin/env python3
"""Seed de UC-12 FOCUS marts in de Fabric workspace.

Eind-tot-eind:
  1. Upload `data-generation/focus-test.csv` naar
     `Files/uc12_seed/focus-test.csv` in `uc11_lakehouse` (OneLake DFS).
  2. Upload notebook `uc12_focus_seed` to the workspace (REST).
  3. Trigger het notebook met workspace_id + lakehouse_id parameters.
  4. Poll tot de notebook-run klaar is.
  5. Refresh het `uc12_focus_finops` semantic model zodat Direct Lake
     reframet tegen de nieuwe Delta-tabellen.
  6. Verifieer dat de 5 marts zichtbaar zijn in de lakehouse tables-list.

Gebruik:
    set -a; source secrets/local/uc11-multiplatform.env; set +a
    python3 scripts/fabric-seed-uc12.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "platform" / "11-airflow" / "include"))

from fabric_helpers import (  # noqa: E402
    FABRIC_ENDPOINT,
    FABRIC_LAKEHOUSE_ID,
    FABRIC_WORKSPACE_ID,
    ONELAKE_SCOPE,
    get_token,
    list_items,
    list_lakehouse_tables,
    request,
    trigger_notebook,
    wait_for_operation,
)

CSV_LOCAL = REPO_ROOT / "data-generation" / "focus-test.csv"
NOTEBOOK_FILE = (
    REPO_ROOT / "platform" / "11-airflow" / "fabric-notebooks" / "uc12_focus_seed.ipynb"
)
NOTEBOOK_NAME = "uc12_focus_seed"
SEMANTIC_MODEL_NAME = "uc12_focus_finops"

# Power BI Datasets API leeft naast de Fabric REST API en is nodig voor
# semantic-model refresh-triggers; aparte scope, aparte hostname.
POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
POWERBI_ENDPOINT = "https://api.powerbi.com/v1.0/myorg"

EXPECTED_MARTS = (
    "mart_uc12_focus_spend_monthly",
    "mart_uc12_focus_service_breakdown",
    "mart_uc12_focus_commitment_utilization",
    "mart_uc12_focus_top_resources",
    "mart_uc12_focus_savings",
)


# ─── OneLake DFS upload ────────────────────────────────────────────────
def _dfs_url(relative_path: str) -> str:
    """OneLake DFS URL for a Files/-pad in uc11_lakehouse."""
    return (
        f"https://onelake.dfs.fabric.microsoft.com/"
        f"{FABRIC_WORKSPACE_ID}/{FABRIC_LAKEHOUSE_ID}/Files/"
        f"{relative_path.lstrip('/')}"
    )


def _onelake_request(
    method: str, url: str, token: str, body: bytes | None = None,
    extra_headers: dict | None = None,
) -> tuple[int, dict, bytes]:
    """Laagje boven urllib for the OneLake DFS REST API."""
    headers = {"Authorization": f"Bearer {token}"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def upload_csv_to_onelake(local_path: Path, relative_path: str) -> None:
    """Upload een bestand naar OneLake Files via DLS Gen2 3-step flow.

    1. PUT ?resource=file — maakt lege file
    2. PATCH ?action=append&position=0 — voegt body toe
    3. PATCH ?action=flush&position=<size> — committeert
    """
    if not local_path.exists():
        raise FileNotFoundError(f"{local_path} bestaat niet")
    body = local_path.read_bytes()
    size = len(body)

    storage_token = get_token(ONELAKE_SCOPE)
    base_url = _dfs_url(relative_path)
    print(f"upload  {local_path.name}  →  {base_url}  ({size:,} bytes)")

    # 1. create empty
    status, _, payload = _onelake_request(
        "PUT", f"{base_url}?resource=file", storage_token,
        extra_headers={"Content-Length": "0"},
    )
    if status not in (200, 201):
        raise RuntimeError(f"create file {status}: {payload[:300]!r}")

    # 2. append in chunks van 4MB (small CSV past in één chunk).
    chunk_size = 4 * 1024 * 1024
    offset = 0
    while offset < size:
        chunk = body[offset : offset + chunk_size]
        status, _, payload = _onelake_request(
            "PATCH",
            f"{base_url}?action=append&position={offset}",
            storage_token,
            body=chunk,
            extra_headers={
                "Content-Length": str(len(chunk)),
                "Content-Type": "application/octet-stream",
            },
        )
        if status not in (200, 202):
            raise RuntimeError(f"append @{offset} {status}: {payload[:300]!r}")
        offset += len(chunk)

    # 3. flush
    status, _, payload = _onelake_request(
        "PATCH",
        f"{base_url}?action=flush&position={size}",
        storage_token,
        extra_headers={"Content-Length": "0"},
    )
    if status not in (200, 202):
        raise RuntimeError(f"flush {status}: {payload[:300]!r}")
    print(f"  ✓ uploaded {size:,} bytes")


# ─── Notebook upload ───────────────────────────────────────────────────
import base64


def upload_notebook(token: str, name: str, file: Path) -> str:
    """Upload of update een Fabric notebook. Returnt het item-ID."""
    payload_b64 = base64.b64encode(file.read_bytes()).decode("ascii")
    parts = [
        {
            "path": "notebook-content.ipynb",
            "payload": payload_b64,
            "payloadType": "InlineBase64",
        }
    ]
    body = {"definition": {"parts": parts, "format": "ipynb"}}

    existing = {n["displayName"]: n["id"] for n in list_items(token, "Notebook")}
    if name in existing:
        item_id = existing[name]
        url = (
            f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}"
            f"/notebooks/{item_id}/updateDefinition"
        )
        status, headers, resp = request("POST", url, token, body)
        if status == 202:
            loc = headers.get("Location") or headers.get("location")
            if loc:
                wait_for_operation(token, loc)
        elif status not in (200, 204):
            raise RuntimeError(f"updateDefinition {status}: {resp}")
        print(f"  ✓ notebook '{name}' geüpdatet (id {item_id})")
        return item_id

    body["displayName"] = name
    url = f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}/notebooks"
    status, headers, resp = request("POST", url, token, body)
    if status in (200, 201):
        new_id = resp["id"]
    elif status == 202:
        loc = headers.get("Location") or headers.get("location")
        if not loc:
            raise RuntimeError(f"create 202 zonder Location: {resp}")
        wait_for_operation(token, loc)
        items = {n["displayName"]: n["id"] for n in list_items(token, "Notebook")}
        new_id = items.get(name)
        if not new_id:
            raise RuntimeError("create notebook 202: kan id niet terugvinden")
    else:
        raise RuntimeError(f"create notebook {status}: {resp}")
    print(f"  ✓ notebook '{name}' aangemaakt (id {new_id})")
    return new_id


# ─── Semantic model refresh ────────────────────────────────────────────
def refresh_semantic_model(token_fabric: str, model_name: str) -> None:
    """Trigger Direct Lake reframe via Power BI Datasets API.

    Direct Lake datasets auto-frame'n automatisch op data-wijzigingen
    (`automatic updates = ON`, default), dus deze stap is optioneel —
    handig voor demo-runs waar je niet wilt wachten tot Fabric het
    automatisch oppakt. Mislukt-graceful: een 401/404 hier blokkeert
    nooit de pipeline.
    """
    # Lookup via Fabric API (al ge-authoriseerd), refresh via PBI API.
    models = [
        m for m in list_items(token_fabric, "SemanticModel")
        if m["displayName"] == model_name
    ]
    if not models:
        print(f"  ! semantic model '{model_name}' niet gevonden — skip refresh")
        return
    mid = models[0]["id"]

    try:
        pbi_token = get_token(POWERBI_SCOPE)
    except Exception as e:
        print(f"  ! kan geen PBI-token krijgen ({e}) — skip; auto-frame doet het")
        return

    url = (
        f"{POWERBI_ENDPOINT}/groups/{FABRIC_WORKSPACE_ID}/datasets/{mid}/refreshes"
    )
    # Direct Lake reframe = type 'automatic' (geen volledige reload).
    status, _, resp = request("POST", url, pbi_token, {"type": "automatic"})
    if status in (200, 202):
        print(f"  ✓ reframe getriggerd voor '{model_name}' ({mid})")
    else:
        print(
            f"  ! reframe status={status}: {resp}\n"
            "    (geen probleem — Direct Lake auto-update doet het automatisch)"
        )


# ─── Main flow ─────────────────────────────────────────────────────────
def main() -> None:
    if not os.environ.get("FABRIC_TENANT_ID"):
        print(
            "FABRIC_TENANT_ID niet gezet. Run:\n"
            "  set -a; source secrets/local/uc11-multiplatform.env; set +a",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[1/6] CSV uploaden naar OneLake Files")
    upload_csv_to_onelake(CSV_LOCAL, "uc12_seed/focus-test.csv")

    print("\n[2/6] Notebook uploaden naar workspace")
    token = get_token()
    nb_id = upload_notebook(token, NOTEBOOK_NAME, NOTEBOOK_FILE)

    print("\n[3/6] Notebook triggeren")
    op_url = trigger_notebook(
        token,
        nb_id,
        parameters={
            "workspace_id": FABRIC_WORKSPACE_ID,
            "lakehouse_id": FABRIC_LAKEHOUSE_ID,
            "csv_relative_path": "uc12_seed/focus-test.csv",
        },
    )
    print(f"  ✓ operation: {op_url}")

    print("\n[4/6] Wachten tot notebook klaar is (max 30min)")
    wait_for_operation(token, op_url, timeout_s=1800, poll_interval_s=20)
    print("  ✓ notebook completed")

    print("\n[5/6] Semantic model refresh triggeren")
    refresh_semantic_model(token, SEMANTIC_MODEL_NAME)

    print("\n[6/6] Verifiëren dat de marts zichtbaar zijn in het lakehouse")
    found = set()
    for attempt in range(6):  # tot 3min waiting voor sync
        tables = set(list_lakehouse_tables(token))
        found = tables & set(EXPECTED_MARTS)
        if found == set(EXPECTED_MARTS):
            break
        time.sleep(30)
    missing = set(EXPECTED_MARTS) - found
    if missing:
        print(f"  ! ontbrekende marts: {sorted(missing)}")
        print(f"  → gevonden tabellen: {sorted(found)}")
        sys.exit(2)
    print(f"  ✓ alle 5 marts zichtbaar: {sorted(found)}")
    print(
        "\nKlaar. Open het rapport op "
        "https://app.fabric.microsoft.com/groups/"
        f"{FABRIC_WORKSPACE_ID}/reports/3f508254-867b-4b58-9c7d-ebafb0947df2"
    )


if __name__ == "__main__":
    main()
