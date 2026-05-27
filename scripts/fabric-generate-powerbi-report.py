#!/usr/bin/env python3
"""Genereer PBIR-bestanden voor uc11_customer_journey Power BI rapport.

Mirror van het Superset uc11_customer_journey dashboard (12 visuals in 5 rijen).
Gebruikt DAX measures (gedefinieerd in model.bim) i.p.v. inline aggregations,
en `cardVisual` i.p.v. `card` — beide nodig om visuals te laten renderen.

Output: platform/12-powerbi/uc11_customer_journey/Report/...
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "platform" / "12-powerbi" / "uc11_customer_journey" / "Report"

PAGE_ID = "uc11dashpage1"
PAGE_W, PAGE_H = 1280, 1040

VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"


# ─── Field projection builders ───────────────────────────────────────
def measure(entity: str, prop: str) -> dict:
    """Projection refererend naar een DAX measure in het semantic model."""
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop,
            }
        },
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }


def column(entity: str, prop: str) -> dict:
    """Projection voor een kale kolom (groupby / axis / row)."""
    return {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop,
            }
        },
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }


# ─── Visual builder ──────────────────────────────────────────────────
def visual(
    name: str,
    x: int, y: int, w: int, h: int,
    visual_type: str,
    query_state: dict,
    title: str | None = None,
) -> dict:
    v = {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {
            "x": x, "y": y, "z": 1000,
            "height": h, "width": w, "tabOrder": 1000,
        },
        "visual": {
            "visualType": visual_type,
            "query": {"queryState": query_state},
            "drillFilterOtherVisuals": True,
        },
    }
    if title:
        v["visual"]["visualContainerObjects"] = {
            "title": [{
                "properties": {
                    "text": {"expr": {"Literal": {"Value": f"'{title}'"}}}
                }
            }]
        }
    return v


# ─── De 12 visuals ───────────────────────────────────────────────────
def all_visuals() -> list[dict]:
    visuals = []

    # ─── Rij 1: 4 KPI cards (y=16, h=120) ─────────────────────────
    visuals.append(visual(
        "v01_kpi_clienten", 16, 16, 308, 120, "cardVisual",
        {"Data": {"projections": [measure("klantreis_events", "Aantal_clienten")]}},
        title="Unieke cliënten in klantreis",
    ))
    visuals.append(visual(
        "v02_kpi_events", 332, 16, 308, 120, "cardVisual",
        {"Data": {"projections": [measure("klantreis_events", "Aantal_events")]}},
        title="Totaal events",
    ))
    visuals.append(visual(
        "v03_kpi_fases", 648, 16, 308, 120, "cardVisual",
        {"Data": {"projections": [measure("klantreis_phases", "Aantal_fases")]}},
        title="Totaal fase-overgangen",
    ))
    visuals.append(visual(
        "v04_kpi_duur", 964, 16, 300, 120, "cardVisual",
        {"Data": {"projections": [measure("klantreis_phases", "Gem_duur_dagen")]}},
        title="Gem. fase-duur (dagen)",
    ))

    # ─── Rij 2: 2 line charts (y=144, h=240) ───────────────────────
    visuals.append(visual(
        "v05_line_events_per_maand", 16, 144, 624, 240, "lineChart",
        {
            "Category": {"projections": [column("klantreis_events", "event_date")]},
            "Y": {"projections": [measure("klantreis_events", "Aantal_events")]},
            "Series": {"projections": [column("klantreis_events", "domein")]},
        },
        title="Events per maand — alle domeinen",
    ))
    visuals.append(visual(
        "v06_line_fases_per_maand", 648, 144, 616, 240, "lineChart",
        {
            "Category": {"projections": [column("klantreis_phases", "fase_start_ts")]},
            "Y": {"projections": [measure("klantreis_phases", "Aantal_fases")]},
            "Series": {"projections": [column("klantreis_phases", "fase")]},
        },
        title="Nieuwe fases per maand",
    ))

    # ─── Rij 3: 3 pie/donut charts (y=400, h=240) ──────────────────
    visuals.append(visual(
        "v07_pie_events_per_domein", 16, 400, 413, 240, "donutChart",
        {
            "Category": {"projections": [column("klantreis_events", "domein")]},
            "Y": {"projections": [measure("klantreis_events", "Aantal_events")]},
        },
        title="Events per domein",
    ))
    visuals.append(visual(
        "v08_pie_fases_per_type", 437, 400, 413, 240, "donutChart",
        {
            "Category": {"projections": [column("klantreis_phases", "fase")]},
            "Y": {"projections": [measure("klantreis_phases", "Aantal_fases")]},
        },
        title="Fases per type",
    ))
    visuals.append(visual(
        "v09_pie_events_per_regio", 858, 400, 406, 240, "donutChart",
        {
            "Category": {"projections": [column("klantreis_events", "regio_code")]},
            "Y": {"projections": [measure("klantreis_events", "Aantal_events")]},
        },
        title="Events per regio (WIA)",
    ))

    # ─── Rij 4: 2 bar charts (y=656, h=220) ────────────────────────
    visuals.append(visual(
        "v10_bar_top_event_types", 16, 656, 624, 220, "clusteredBarChart",
        {
            "Category": {"projections": [column("klantreis_events", "event_type")]},
            "Y": {"projections": [measure("klantreis_events", "Aantal_events")]},
        },
        title="Top event-types",
    ))
    visuals.append(visual(
        "v11_bar_duur_per_fase", 648, 656, 616, 220, "clusteredBarChart",
        {
            "Category": {"projections": [column("klantreis_phases", "fase")]},
            "Y": {"projections": [measure("klantreis_phases", "Gem_duur_dagen")]},
        },
        title="Gem. duur per fase-type (dagen)",
    ))

    # ─── Rij 5: 1 tabel (y=892, h=132) ─────────────────────────────
    visuals.append(visual(
        "v12_tbl_top_clienten", 16, 892, 1248, 132, "tableEx",
        {
            "Values": {
                "projections": [
                    column("klantreis_events", "bsn"),
                    measure("klantreis_events", "Aantal_events"),
                    measure("klantreis_events", "Aantal_domeinen"),
                ],
            },
        },
        title="Cliënten met meeste events",
    ))
    return visuals


# ─── Root files ──────────────────────────────────────────────────────
def definition_pbir(semantic_model_id: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {
            "byConnection": {
                "connectionString": f"semanticmodelid={semantic_model_id}"
            }
        },
    }


def version_json() -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    }


def report_json() -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY24SU10",
                "type": "SharedResources",
                "reportVersionAtImport": {
                    "visual": "1.8.97", "report": "2.0.97", "page": "1.3.97",
                },
            }
        },
        "settings": {
            "useStylableVisualContainerHeader": True,
            "useEnhancedTooltips": True,
            "defaultDrillFilterOtherVisuals": True,
        },
    }


def pages_json() -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [PAGE_ID],
        "activePageName": PAGE_ID,
    }


def page_json() -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": PAGE_ID,
        "displayName": "UC-11 Integrale Klantreis",
        "displayOption": "FitToPage",
        "height": PAGE_H,
        "width": PAGE_W,
        "pageBinding": {
            "name": "uc11binding",
            "type": "Default",
            "parameters": [],
            "acceptsFilterContext": "None",
        },
    }


def main(semantic_model_id: str) -> None:
    if OUT_DIR.exists():
        for p in sorted(OUT_DIR.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "definition.pbir").write_text(json.dumps(definition_pbir(semantic_model_id), indent=2))
    defin = OUT_DIR / "definition"
    defin.mkdir(exist_ok=True)
    (defin / "version.json").write_text(json.dumps(version_json(), indent=2))
    (defin / "report.json").write_text(json.dumps(report_json(), indent=2))

    pages = defin / "pages"
    pages.mkdir(exist_ok=True)
    (pages / "pages.json").write_text(json.dumps(pages_json(), indent=2))

    page = pages / PAGE_ID
    page.mkdir(exist_ok=True)
    (page / "page.json").write_text(json.dumps(page_json(), indent=2))

    visuals_dir = page / "visuals"
    visuals_dir.mkdir(exist_ok=True)
    for v in all_visuals():
        vdir = visuals_dir / v["name"]
        vdir.mkdir(exist_ok=True)
        (vdir / "visual.json").write_text(json.dumps(v, indent=2))

    n_files = sum(1 for _ in OUT_DIR.rglob("*") if _.is_file())
    print(f"PBIR gegenereerd in {OUT_DIR} ({n_files} files)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.path.insert(0, str(REPO_ROOT / "platform" / "11-airflow" / "include"))
        from fabric_helpers import get_token, list_items
        if not os.environ.get("FABRIC_TENANT_ID"):
            print("Geef SemanticModel-ID als argument of zet Fabric env-vars.", file=sys.stderr)
            sys.exit(1)
        models = [m for m in list_items(get_token(), "SemanticModel") if m["displayName"] == "uc11_customer_journey"]
        if not models:
            print("SemanticModel 'uc11_customer_journey' niet gevonden in workspace.", file=sys.stderr)
            sys.exit(1)
        sid = models[0]["id"]
        print(f"Auto-discovered SemanticModel ID: {sid}")
    else:
        sid = sys.argv[1]
    main(sid)
