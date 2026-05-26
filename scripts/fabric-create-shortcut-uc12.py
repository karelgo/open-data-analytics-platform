#!/usr/bin/env python3
"""Maak OneLake S3-shortcuts voor de UC-12 marts → s3://odap-gold/uc12_focus_finops/...

End-state architectuur: data leeft in MinIO, Power BI Direct Lake leest via een
OneLake-shortcut alsof het lokaal in `uc11_lakehouse` staat. Nul data-copy.

5 shortcuts, één per mart, op `Tables/` niveau zodat ze als `dbo.<naam>`
verschijnen in de SQL endpoint — dat is wat het bestaande UC-12 semantic
model verwacht (zie platform/12-powerbi/uc12_focus_finops/SemanticModel/model.bim).

Voorvereisten:
  1. MinIO publiek bereikbaar (zie `scripts/fabric-probe-minio.py`).
  2. Een Fabric Connection naar het S3-endpoint is reeds aangemaakt in de
     workspace — Microsoft heeft de Connections-API in beweging, dus voor nu:
     aanmaken via UI eenmalig (`Workspace → Manage connections → New →
     S3 Compatible` met de MinIO endpoint + access/secret key).
     De connection-ID komt mee als `--connection-id` argument.

Gebruik:
    set -a; source secrets/local/uc11-multiplatform.env; set +a
    python3 scripts/fabric-create-shortcut-uc12.py \\
        --endpoint https://minio.example.com \\
        --bucket   odap-gold \\
        --prefix   uc12_focus_finops \\
        --connection-id  <guid-uit-fabric-UI>

Met `--dry-run` print de script alleen wat ie zou doen (geen REST-calls).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "platform" / "11-airflow" / "include"))

from fabric_helpers import (  # noqa: E402
    FABRIC_ENDPOINT,
    FABRIC_LAKEHOUSE_ID,
    FABRIC_WORKSPACE_ID,
    get_token,
    request,
)

MARTS = (
    "mart_uc12_focus_spend_monthly",
    "mart_uc12_focus_service_breakdown",
    "mart_uc12_focus_commitment_utilization",
    "mart_uc12_focus_top_resources",
    "mart_uc12_focus_savings",
)

OK = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


def list_existing_shortcuts(token: str) -> list[dict]:
    """Returnt alle bestaande shortcuts onder het uc11_lakehouse."""
    url = (
        f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}"
        f"/items/{FABRIC_LAKEHOUSE_ID}/shortcuts"
    )
    status, _, payload = request("GET", url, token)
    if status != 200:
        raise RuntimeError(f"list shortcuts {status}: {payload}")
    return payload.get("value", [])


def create_shortcut(
    token: str,
    name: str,
    path: str,
    endpoint: str,
    bucket: str,
    subpath: str,
    connection_id: str,
) -> dict:
    """POST een nieuwe S3-shortcut.

    Volgens Microsoft Learn — `target.s3Compatible` werkt voor MinIO en
    andere S3-API-compat providers; `target.amazonS3` is alleen voor
    echt-AWS endpoints. Beide nemen `connectionId`.
    """
    url = (
        f"{FABRIC_ENDPOINT}/workspaces/{FABRIC_WORKSPACE_ID}"
        f"/items/{FABRIC_LAKEHOUSE_ID}/shortcuts"
    )
    body = {
        "name": name,
        "path": path,
        "target": {
            "s3Compatible": {
                "connectionId": connection_id,
                "location": endpoint,
                "bucket": bucket,
                "subpath": subpath,
            }
        },
    }
    status, _, payload = request("POST", url, token, body)
    if status in (200, 201):
        return payload
    if status == 409:
        # Conflict = al aanwezig met deze (path, name). Niet fataal.
        return {"_already_exists": True, "response": payload}
    raise RuntimeError(f"create shortcut '{name}' {status}: {payload}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--endpoint",
        required=True,
        help="MinIO HTTPS endpoint, bv. https://minio.example.com",
    )
    ap.add_argument(
        "--bucket",
        default="odap-gold",
        help="S3-bucket (default: odap-gold)",
    )
    ap.add_argument(
        "--prefix",
        default="uc12_focus_finops",
        help="Key-prefix onder de bucket waarin elke mart als eigen folder ligt"
        " (default: uc12_focus_finops). Verwacht layout"
        " s3://<bucket>/<prefix>/<mart_name>/_delta_log/...",
    )
    ap.add_argument(
        "--connection-id",
        required=True,
        help="GUID van de S3-compat Connection in de Fabric workspace",
    )
    ap.add_argument(
        "--marts",
        default=",".join(MARTS),
        help="Comma-separated mart-namen. Default: alle 5 UC-12 marts.",
    )
    ap.add_argument(
        "--shortcut-path",
        default="Tables",
        help="Fabric path waar de shortcuts onder geplaatst worden (default: Tables)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(
        f"Workspace : {FABRIC_WORKSPACE_ID}\n"
        f"Lakehouse : {FABRIC_LAKEHOUSE_ID}\n"
        f"Endpoint  : {args.endpoint}\n"
        f"Bucket    : {args.bucket}\n"
        f"Prefix    : {args.prefix}/\n"
        f"Path      : {args.shortcut_path}/"
    )

    marts = [m.strip() for m in args.marts.split(",") if m.strip()]
    print(f"Te maken  : {len(marts)} shortcut(s)")

    if args.dry_run:
        print("\n--dry-run: geen REST-calls. Plan:")
        for m in marts:
            sub = f"/{args.prefix}/{m}"
            print(f"  → Tables/{m}  ←  s3://{args.bucket}{sub}")
        return

    token = get_token()

    existing = {(s.get("path", ""), s.get("name", "")) for s in list_existing_shortcuts(token)}
    print(f"\nBestaande shortcuts: {len(existing)}")

    created = 0
    skipped = 0
    failed: list[str] = []

    for mart in marts:
        key = (args.shortcut_path, mart)
        subpath = f"/{args.prefix}/{mart}"
        target_uri = f"s3://{args.bucket}{subpath}"
        if key in existing:
            print(f"  {OK} {args.shortcut_path}/{mart}  bestaat al — skip")
            skipped += 1
            continue
        try:
            create_shortcut(
                token=token,
                name=mart,
                path=args.shortcut_path,
                endpoint=args.endpoint,
                bucket=args.bucket,
                subpath=subpath,
                connection_id=args.connection_id,
            )
            print(f"  {OK} {args.shortcut_path}/{mart}  →  {target_uri}")
            created += 1
        except RuntimeError as e:
            print(f"  {FAIL} {args.shortcut_path}/{mart}: {e}")
            failed.append(mart)

    print(
        f"\nResultaat: {created} aangemaakt, {skipped} bestond al, "
        f"{len(failed)} faalde"
    )
    if failed:
        sys.exit(1)
    print(
        "\nVolgende stap: refresh het semantic model zodat Direct Lake de\n"
        "shortcut'd tabellen oppikt:\n"
        "  python3 -c \"\\\n"
        "    import sys; sys.path.insert(0,'platform/11-airflow/include');\\\n"
        "    from fabric_helpers import get_token, list_items, request;\\\n"
        "    tok=get_token('https://analysis.windows.net/powerbi/api/.default');\\\n"
        "    ws='$FABRIC_WORKSPACE_ID';\\\n"
        "    print('manual: open Fabric UI → uc12_focus_finops → Refresh now')\""
    )


if __name__ == "__main__":
    main()
