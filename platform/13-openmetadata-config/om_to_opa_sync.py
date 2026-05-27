"""Reverse Metadata: OpenMetadata tags → OPA bundle data.json.

OM 1.5 heeft geen native Reverse Metadata (community feature pas vanaf
1.7+). We implementeren het hier custom: deze CronJob leest de
`Purpose limitation.*` tags van elke Trino-tabel in OM en updatet
`role_mappings.resource_purposes` in de OPA-bundle ConfigMap.
Stackable's OPA-operator herlaadt automatisch via de
`opa.stackable.tech/bundle: true` label.

Sluit het lint dbt-meta → enricher → OM → OPA → Trino-rij-/kolom-policy.

Strategy:
  1. GET /api/v1/tables (paginated) met fields=tags.
  2. Per tabel: extract Purpose limitation.* tags → lowercase purpose-limitation-namen.
  3. Aggregeer per "<catalog>.<schema>.*" glob — UNION van alle tabel-tags
     binnen die schema.
  4. Read opa-trino-bundle.data.json.
  5. Merge: nieuwe OM-afgeleide entries overschrijven, bestaande
     (handmatige) entries die niet door OM bestreken worden blijven staan.
  6. PATCH de ConfigMap.

Env-vars:
  OM_URL                http://openmetadata.odap-meta.svc.cluster.local:8585
  OM_JWT_TOKEN          admin/bot JWT (ViewAll op tables)
  OM_TRINO_SERVICE      trino (default — beperkt scan tot deze service)
  OPA_CONFIGMAP_NS      odap-platform (default)
  OPA_CONFIGMAP_NAME    opa-trino-bundle (default)
  DRY_RUN               "true" om alleen logging zonder PATCH
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from urllib.parse import urlencode

import requests

OM_URL = os.environ.get(
    "OM_URL", "http://openmetadata.odap-meta.svc.cluster.local:8585"
).rstrip("/")
OM_TOKEN = os.environ["OM_JWT_TOKEN"]
TRINO_SERVICE = os.environ.get("OM_TRINO_SERVICE", "trino")

CM_NS = os.environ.get("OPA_CONFIGMAP_NS", "odap-platform")
CM_NAME = os.environ.get("OPA_CONFIGMAP_NAME", "opa-trino-bundle")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ("1", "true", "yes")

KUBE_HOST = "https://kubernetes.default.svc"
SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
SA_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

OM_HEADERS = {
    "Authorization": f"Bearer {OM_TOKEN}",
    "Content-Type": "application/json",
}


def log(msg: str) -> None:
    print(f"[om-to-opa] {msg}", flush=True)


def list_tables() -> list[dict]:
    """Paginate over /api/v1/tables?service=<svc>&fields=tags."""
    out: list[dict] = []
    after = None
    while True:
        params = {
            "fields": "tags",
            "service": TRINO_SERVICE,
            "limit": "100",
        }
        if after:
            params["after"] = after
        url = f"{OM_URL}/api/v1/tables?{urlencode(params)}"
        r = requests.get(url, headers=OM_HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("data", []))
        paging = data.get("paging", {})
        after = paging.get("after")
        if not after:
            break
    return out


def _glob_from_fqn(fqn: str) -> str | None:
    """trino.gold.uc01_claims_funnel.mart_x → gold.uc01_claims_funnel.*

    Service-prefix verwijderen, schema-glob bouwen. FQN-segmenten met
    quotes worden gestript (OM kwoot soms namen met punten/dashes).
    """
    parts = []
    cur = ""
    in_quote = False
    for ch in fqn:
        if ch == '"':
            in_quote = not in_quote
        elif ch == "." and not in_quote:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        parts.append(cur)
    if len(parts) < 4:
        return None
    # parts = [service, database, schema, table]
    return f"{parts[1]}.{parts[2]}.*"


def extract_purpose-limitationen(tags: list[dict]) -> set[str]:
    out: set[str] = set()
    for t in tags or []:
        fqn = t.get("tagFQN") or ""
        if fqn.startswith("Purpose limitation."):
            out.add(fqn[len("Purpose limitation."):].lower())
    return out


def aggregate_resource_purposes(tables: list[dict]) -> dict[str, list[str]]:
    by_glob: dict[str, set[str]] = defaultdict(set)
    for tbl in tables:
        fqn = tbl.get("fullyQualifiedName") or ""
        glob = _glob_from_fqn(fqn)
        if not glob:
            continue
        db = extract_purpose-limitationen(tbl.get("tags") or [])
        by_glob[glob].update(db)
    return {g: sorted(s) for g, s in by_glob.items() if s}


def get_configmap() -> dict:
    with open(SA_TOKEN_PATH) as f:
        sa_token = f.read().strip()
    r = requests.get(
        f"{KUBE_HOST}/api/v1/namespaces/{CM_NS}/configmaps/{CM_NAME}",
        headers={
            "Authorization": f"Bearer {sa_token}",
            "Accept": "application/json",
        },
        timeout=15,
        verify=SA_CA_PATH,
    )
    r.raise_for_status()
    return r.json()


def patch_configmap_data(new_data_json: str) -> None:
    """Strategic merge patch — vervang alleen data.json zonder andere keys
    aan te raken. ConfigMap re-load gebeurt automatisch door Stackable
    OPA-operator (label opa.stackable.tech/bundle: true)."""
    with open(SA_TOKEN_PATH) as f:
        sa_token = f.read().strip()
    body = {"data": {"data.json": new_data_json}}
    r = requests.patch(
        f"{KUBE_HOST}/api/v1/namespaces/{CM_NS}/configmaps/{CM_NAME}",
        headers={
            "Authorization": f"Bearer {sa_token}",
            "Content-Type": "application/strategic-merge-patch+json",
            "Accept": "application/json",
        },
        data=json.dumps(body),
        timeout=15,
        verify=SA_CA_PATH,
    )
    if r.status_code not in (200, 201):
        log(f"  ! PATCH faalde: status={r.status_code} body={r.text[:200]}")
        r.raise_for_status()
    log(f"  ✓ opa-trino-bundle.data.json gepatched in {CM_NS}")


def main() -> int:
    log(f"Read OM tables (service={TRINO_SERVICE})")
    tables = list_tables()
    log(f"  {len(tables)} tabellen")

    om_map = aggregate_resource_purposes(tables)
    log(f"  {len(om_map)} schema-globs met Purpose limitation-tags")
    for g, ds in sorted(om_map.items()):
        log(f"    {g} → {ds}")

    if not om_map:
        log("Geen OM-afgeleide purpose-limitation-mappings — sla update over.")
        return 0

    log(f"Lees OPA ConfigMap {CM_NS}/{CM_NAME}")
    cm = get_configmap()
    raw = (cm.get("data") or {}).get("data.json", "{}")
    try:
        opa_data = json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"  ! data.json niet geldige JSON: {e}")
        return 1

    role_mappings = opa_data.setdefault("role_mappings", {})
    existing = role_mappings.get("resource_purposes", {})
    merged = dict(existing)  # behoud entries die OM niet bestrijkt
    for glob, purposes in om_map.items():
        merged[glob] = purposes  # OM-afgeleide wint
    role_mappings["resource_purposes"] = merged

    new_raw = json.dumps(opa_data, indent=2, sort_keys=True)

    if DRY_RUN:
        log("[DRY_RUN] zou PATCH'en met:")
        log(new_raw[:600] + "…")
        return 0

    if new_raw == raw:
        log("Geen wijziging in data.json (idempotent).")
        return 0

    patch_configmap_data(new_raw)
    log(f"Klaar. {len(merged)} resource_purpose-entries (was {len(existing)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
