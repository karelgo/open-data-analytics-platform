#!/usr/bin/env python3
"""Upload Power BI semantic model + report to the Fabric workspace.

Idempotent: detecteert bestaande items by displayName en doet
updateDefinition; anders POST naar create endpoint.

Gebruik:
    set -a; source secrets/local/uc11-multiplatform.env; set +a
    python3 scripts/fabric-upload-powerbi.py [--semanticmodel-only|--report-only]
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

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

def _project_paths(project_name: str):
    root = REPO_ROOT / "platform" / "12-powerbi" / project_name
    return root, root / "SemanticModel", root / "Report"


def _collect_parts(root: Path) -> list[dict]:
    """Verzamel alle files onder root als InlineBase64 parts."""
    parts = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        parts.append({"path": rel, "payload": b64, "payloadType": "InlineBase64"})
    return parts


ITEM_TYPE_FILTER = {"semanticModels": "SemanticModel", "reports": "Report"}


def _create_or_update(
    token: str,
    item_type: str,        # "semanticModels" | "reports"
    display_name: str,
    parts: list[dict],
) -> str:
    """POST naar create; bij bestaande item PUT naar updateDefinition.

    Returnt het item-ID.
    """
    existing = {it["displayName"]: it["id"] for it in list_items(token, ITEM_TYPE_FILTER[item_type])}
    body = {"definition": {"parts": parts}}

    if display_name in existing:
        item_id = existing[display_name]
        url = f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}/{item_type}/{item_id}/updateDefinition"
        status, headers, payload = request("POST", url, token, body)
        if status in (200, 204):
            return item_id
        if status == 202:
            op = headers.get("Location") or headers.get("location")
            if op:
                wait_for_operation(token, op)
                return item_id
        raise RuntimeError(f"updateDefinition {item_type} {status}: {payload}")

    # Create new
    body["displayName"] = display_name
    url = f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}/{item_type}"
    status, headers, payload = request("POST", url, token, body)
    if status in (200, 201):
        return payload["id"]
    if status == 202:
        op = headers.get("Location") or headers.get("location")
        if op:
            wait_for_operation(token, op)
            # Re-query om de id te vinden
            type_filter = "SemanticModel" if "semantic" in item_type else "Report"
            for it in list_items(token, type_filter):
                if it["displayName"] == display_name:
                    return it["id"]
        raise RuntimeError(f"create {item_type} 202 zonder Location: {payload}")
    raise RuntimeError(f"create {item_type} {status}: {payload}")


def upload_semantic_model(token: str, project_name: str, display_name: str) -> str:
    _, sm_dir, _ = _project_paths(project_name)
    parts = _collect_parts(sm_dir)
    print(f"SemanticModel {display_name}: {len(parts)} files")
    for p in parts:
        print(f"  - {p['path']}")
    item_id = _create_or_update(token, "semanticModels", display_name, parts)
    print(f"  → id {item_id}")
    return item_id


def upload_report(token: str, project_name: str, display_name: str) -> str:
    _, _, report_dir = _project_paths(project_name)
    parts = _collect_parts(report_dir)
    if not parts:
        print("Report dir is leeg — skip report upload")
        return ""
    print(f"Report {display_name}: {len(parts)} files")
    for p in parts:
        print(f"  - {p['path']}")
    item_id = _create_or_update(token, "reports", display_name, parts)
    print(f"  → id {item_id}")
    return item_id


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="uc11_customer_journey",
                    help="Project dir onder platform/12-powerbi/. Default: uc11_customer_journey (Fabric).")
    ap.add_argument("--semanticmodel-only", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    project = args.project
    # Display names matchen het project (Fabric of Databricks variant).
    sm_name = project  # bv. uc11_customer_journey_databricks
    rpt_name = f"{project}_dashboard"

    token = get_token()
    if not args.report_only:
        upload_semantic_model(token, project, sm_name)
    if not args.semanticmodel_only:
        upload_report(token, project, rpt_name)

    print()
    print("Final state in workspace:")
    for it in list_items(token):
        if it["type"] in ("SemanticModel", "Report"):
            print(f"  - {it['type']:15s} {it['displayName']:30s} {it['id']}")


if __name__ == "__main__":
    main()
