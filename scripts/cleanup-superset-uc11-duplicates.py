#!/usr/bin/env python3
"""Cleanup duplicate UC-11 charts in Superset + rebuild dashboard layout.

Keeps the highest-ID chart for each unique slice_name (= most recently
created with current configs), deletes the rest, and ensures the dashboard
references exactly the 12 kept charts with the proper position_json layout.
"""
import json, sys, os, urllib3
import requests
urllib3.disable_warnings()

URL = "http://localhost:8088"
USER = os.environ["SS_USER"]
PASS = os.environ["SS_PASS"]

UC11_NAMES = [
    "Unieke cliënten in klantreis",
    "Totaal events",
    "Totaal fase-overgangen",
    "Gem. fase-duur (dagen)",
    "Events per maand — alle domeinen",
    "Nieuwe fases per maand",
    "Events per domein",
    "Fases per type",
    "Events per regio (WIA)",
    "Top 10 event-types",
    "Gem. duur per fase-type (dagen)",
    "Cliënten met meeste events (top 50)",
]
# Layout widths matching dashboards-init-job.yaml
WIDTHS = [3, 3, 3, 3, 6, 6, 4, 4, 4, 6, 6, 12]
HEIGHTS = [30, 30, 30, 30, 50, 50, 50, 50, 50, 55, 55, 60]
DASHBOARD_SLUG = "uc11-customer-journey"


def login():
    s = requests.Session()
    s.verify = False
    r = s.post(f"{URL}/api/v1/security/login",
               json={"username": USER, "password": PASS,
                     "provider": "db", "refresh": True})
    r.raise_for_status()
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    r = s.get(f"{URL}/api/v1/security/csrf_token/")
    r.raise_for_status()
    s.headers["X-CSRFToken"] = r.json()["result"]
    s.headers["Referer"] = URL
    return s


def list_all_charts(s):
    rows = []
    page = 0
    while True:
        r = s.get(f"{URL}/api/v1/chart/",
                  params={"q": f"(page:{page},page_size:100)"})
        r.raise_for_status()
        data = r.json().get("result", [])
        if not data:
            break
        rows.extend(data)
        if len(data) < 100:
            break
        page += 1
    return rows


def main():
    s = login()
    all_charts = list_all_charts(s)
    print(f"total charts in Superset: {len(all_charts)}")

    # Group UC-11-named charts by slice_name
    by_name = {}
    for c in all_charts:
        if c["slice_name"] in UC11_NAMES:
            by_name.setdefault(c["slice_name"], []).append(c["id"])

    keep_ids = []
    delete_ids = []
    for name in UC11_NAMES:
        ids = sorted(by_name.get(name, []), reverse=True)  # highest first
        if not ids:
            print(f"  WARN: no chart found for {name}")
            continue
        keep_ids.append(ids[0])
        delete_ids.extend(ids[1:])

    print(f"\nkeep: {keep_ids}")
    print(f"delete ({len(delete_ids)}): {delete_ids}")

    # Bulk-delete via the bulk endpoint (more reliable than per-id DELETE)
    if delete_ids:
        ids_param = "!(" + ",".join(str(i) for i in delete_ids) + ")"
        r = s.delete(f"{URL}/api/v1/chart/?q={ids_param}")
        print(f"\nbulk-delete → {r.status_code}: {r.text[:200]}")

    # Verify
    after = list_all_charts(s)
    uc11_after = [c for c in after if c["slice_name"] in UC11_NAMES]
    print(f"\nUC-11 charts after cleanup: {len(uc11_after)} (expected 12)")
    for c in uc11_after:
        print(f"  id={c['id']:>4}  {c['slice_name']}")

    # Find dashboard
    r = s.get(f"{URL}/api/v1/dashboard/",
              params={"q": f"(filters:!((col:slug,opr:eq,value:{DASHBOARD_SLUG})))"})
    r.raise_for_status()
    dash = r.json()["result"][0]
    did = dash["id"]
    print(f"\ndashboard '{DASHBOARD_SLUG}' id={did}")

    # Re-attach each kept chart to dashboard (chart PUT with dashboards=[did])
    # This is idempotent — sets the M2M to just [did].
    for cid in keep_ids:
        r = s.put(f"{URL}/api/v1/chart/{cid}", json={"dashboards": [did]})
        if r.status_code != 200:
            print(f"  ! chart {cid} → dashboard {did}: {r.status_code} {r.text[:200]}")

    # Rebuild position_json with the kept chart IDs
    layout = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [],
                    "parents": ["ROOT_ID"]},
    }
    row_idx = 0
    current_row_id = None
    current_row_used = 0
    for i, (cid, slice_name, w, h) in enumerate(
            zip(keep_ids, UC11_NAMES, WIDTHS, HEIGHTS)):
        if current_row_id is None or current_row_used + w > 12:
            row_idx += 1
            current_row_id = f"ROW-{row_idx}"
            current_row_used = 0
            layout["GRID_ID"]["children"].append(current_row_id)
            layout[current_row_id] = {
                "type": "ROW", "id": current_row_id, "children": [],
                "parents": ["ROOT_ID", "GRID_ID"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
        chart_block_id = f"CHART-{i+1}"
        layout[current_row_id]["children"].append(chart_block_id)
        layout[chart_block_id] = {
            "type": "CHART", "id": chart_block_id, "children": [],
            "parents": ["ROOT_ID", "GRID_ID", current_row_id],
            "meta": {"chartId": cid, "width": w, "height": h,
                     "sliceName": slice_name},
        }
        current_row_used += w

    r = s.put(f"{URL}/api/v1/dashboard/{did}",
              json={"position_json": json.dumps(layout)})
    if r.status_code != 200:
        print(f"  ! dashboard layout PUT: {r.status_code} {r.text[:300]}")
    else:
        print(f"\n✓ dashboard layout updated — {len(keep_ids)} charts in 5 rows")

    # Final dashboard chart-count
    r = s.get(f"{URL}/api/v1/dashboard/{did}/charts")
    dash_charts = r.json().get("result", [])
    print(f"\ndashboard '{DASHBOARD_SLUG}' now has {len(dash_charts)} chart references")


if __name__ == "__main__":
    main()
