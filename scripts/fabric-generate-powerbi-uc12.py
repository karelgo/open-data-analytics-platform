#!/usr/bin/env python3
"""Genereer Power BI semantic model + PBIR-rapport voor UC-12 (FOCUS FinOps).

Mirror van het Superset uc12-focus-finops dashboard:
  Rij 1 — 4 KPI cards: total effective cost, total list cost, total savings,
          avg commitment coverage
  Rij 2 — 2 line charts: spend per maand × provider, commitment coverage %
          per maand × service-categorie
  Rij 3 — 3 donut charts: spend per service-categorie, regio, environment
  Rij 4 — 2 bar charts: top services, spend per application
  Rij 5 — 1 tabel: top-50 resources

Direct Lake-mode tegen het bestaande `uc11_lakehouse` (zelfde Fabric workspace
+ SQL endpoint host als UC-11; zie secrets/local/uc11-multiplatform.env).

Voorvereiste: de 5 marts MOETEN al in het lakehouse staan. Zie
docs/use-cases/uc12-focus-finops-powerbi.md for the seed-stappen (dbt-
fabricspark target of een one-shot Fabric notebook).

Output:
  platform/12-powerbi/uc12_focus_finops/SemanticModel/  (model.bim + .pbism)
  platform/12-powerbi/uc12_focus_finops/Report/         (PBIR-tree)

Gebruik:
  set -a; source secrets/local/uc11-multiplatform.env; set +a
  python3 scripts/fabric-generate-powerbi-uc12.py
  python3 scripts/fabric-upload-powerbi.py --project uc12_focus_finops
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "platform" / "12-powerbi" / "uc12_focus_finops"
SM_DIR = OUT_DIR / "SemanticModel"
RP_DIR = OUT_DIR / "Report"

# Env-driven — SQL endpoint host komt from the UC-11 lakehouse (gedeeld).
SQL_HOST = os.environ.get(
    "FABRIC_SQL_ENDPOINT_HOST",
    "f7x5z7ufbtoubd2v4iyuhxftm4-vadyhb425gouxeoepoh4ivyyhm.datawarehouse.fabric.microsoft.com",
)
LAKEHOUSE_NAME = os.environ.get("FABRIC_LAKEHOUSE_NAME", "uc11_lakehouse")

PAGE_ID = "uc12dashpage1"
PAGE_W, PAGE_H = 1280, 1040

VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/visualContainer/2.7.0/schema.json"
)


# ═══════════════════════════════════════════════════════════════════════
# SemanticModel: model.bim + definition.pbism
# ═══════════════════════════════════════════════════════════════════════

# Helpers om een kolom-entry compact te schrijven.
def _col(
    name: str,
    dtype: str,
    src_type: str,
    *,
    summarize: str = "none",
    format_str: str | None = None,
    tag_prefix: str = "c",
) -> dict:
    d: dict = {
        "name": name,
        "dataType": dtype,
        "sourceColumn": name,
        "summarizeBy": summarize,
        "lineageTag": f"{tag_prefix}-{name}",
        "sourceLineageTag": name,
        "sourceProviderType": src_type,
    }
    if format_str is not None:
        d["formatString"] = format_str
    return d


def _table(
    short: str,                  # interne naam (en lineageTag-prefix)
    entity: str,                 # SQL-tabel in de lakehouse (mart_uc12_focus_*)
    columns: list[dict],
    measures: list[dict],
) -> dict:
    return {
        "name": short,
        "lineageTag": f"tbl-{short}",
        "sourceLineageTag": f"[dbo].[{entity}]",
        "measures": measures,
        "columns": columns,
        "partitions": [
            {
                "name": f"{short}-partition",
                "mode": "directLake",
                "source": {
                    "type": "entity",
                    "entityName": entity,
                    "schemaName": "dbo",
                    "expressionSource": "DatabaseQuery",
                },
            }
        ],
        "annotations": [],
    }


def _measure(name: str, expr: str, fmt: str, tag: str) -> dict:
    return {
        "name": name,
        "expression": expr,
        "formatString": fmt,
        "lineageTag": f"m-{tag}",
    }


def build_model_bim() -> dict:
    """Bouw het volledige model.bim — 5 tables met DAX measures."""
    # ─── Tabel 1: spend_monthly ────────────────────────────────────────
    spend_monthly = _table(
        short="spend_monthly",
        entity="mart_uc12_focus_spend_monthly",
        columns=[
            _col("billing_month", "dateTime", "datetime2",
                 format_str="yyyy-mm", tag_prefix="sm"),
            _col("provider", "string", "varchar(8000)", tag_prefix="sm"),
            _col("service_category", "string", "varchar(8000)", tag_prefix="sm"),
            _col("charge_category", "string", "varchar(8000)", tag_prefix="sm"),
            _col("billing_currency", "string", "varchar(8000)", tag_prefix="sm"),
            _col("billed_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sm"),
            _col("effective_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sm"),
            _col("list_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sm"),
            _col("savings_amount", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sm"),
            _col("usage_quantity", "double", "float", summarize="sum",
                 format_str="#,##0.0000", tag_prefix="sm"),
            _col("n_charges", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="sm"),
            _col("n_resources", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="sm"),
            _col("n_sub_accounts", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="sm"),
        ],
        measures=[
            _measure("Effective Cost Total",
                     "SUM(spend_monthly[effective_cost])",
                     "\\€#,##0;-\\€#,##0", "sm-effective"),
            _measure("List Cost Total",
                     "SUM(spend_monthly[list_cost])",
                     "\\€#,##0;-\\€#,##0", "sm-list"),
            _measure("Billed Cost Total",
                     "SUM(spend_monthly[billed_cost])",
                     "\\€#,##0;-\\€#,##0", "sm-billed"),
            _measure("Resource Count",
                     "SUM(spend_monthly[n_resources])",
                     "#,##0", "sm-resources"),
        ],
    )

    # ─── Tabel 2: service_breakdown ───────────────────────────────────
    service_breakdown = _table(
        short="service_breakdown",
        entity="mart_uc12_focus_service_breakdown",
        columns=[
            _col("billing_month", "dateTime", "datetime2",
                 format_str="yyyy-mm", tag_prefix="sb"),
            _col("provider", "string", "varchar(8000)", tag_prefix="sb"),
            _col("service_category", "string", "varchar(8000)", tag_prefix="sb"),
            _col("service_name", "string", "varchar(8000)", tag_prefix="sb"),
            _col("region", "string", "varchar(8000)", tag_prefix="sb"),
            _col("environment", "string", "varchar(8000)", tag_prefix="sb"),
            _col("application", "string", "varchar(8000)", tag_prefix="sb"),
            _col("billing_currency", "string", "varchar(8000)", tag_prefix="sb"),
            _col("effective_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sb"),
            _col("billed_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sb"),
            _col("usage_quantity", "double", "float", summarize="sum",
                 format_str="#,##0.0000", tag_prefix="sb"),
            _col("n_resources", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="sb"),
            _col("n_charges", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="sb"),
        ],
        measures=[
            _measure("Service Spend",
                     "SUM(service_breakdown[effective_cost])",
                     "\\€#,##0;-\\€#,##0", "sb-spend"),
        ],
    )

    # ─── Tabel 3: commitment_utilization ──────────────────────────────
    commitment = _table(
        short="commitment",
        entity="mart_uc12_focus_commitment_utilization",
        columns=[
            _col("billing_month", "dateTime", "datetime2",
                 format_str="yyyy-mm", tag_prefix="ci"),
            _col("provider", "string", "varchar(8000)", tag_prefix="ci"),
            _col("service_category", "string", "varchar(8000)", tag_prefix="ci"),
            _col("billing_currency", "string", "varchar(8000)", tag_prefix="ci"),
            _col("committed_spend", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="ci"),
            _col("on_demand_spend", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="ci"),
            _col("dynamic_spend", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="ci"),
            _col("total_spend", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="ci"),
            _col("savings_amount", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="ci"),
            _col("n_active_commitments", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="ci"),
            _col("commitment_coverage_pct", "double", "float",
                 summarize="none", format_str="0.0%", tag_prefix="ci"),
            _col("effective_discount_pct", "double", "float",
                 summarize="none", format_str="0.0%", tag_prefix="ci"),
        ],
        measures=[
            _measure("Avg Commitment Coverage",
                     "AVERAGE(commitment[commitment_coverage_pct])",
                     "0.0%", "ci-cov"),
            _measure("Committed Spend",
                     "SUM(commitment[committed_spend])",
                     "\\€#,##0;-\\€#,##0", "ci-comm"),
            _measure("On-demand Spend",
                     "SUM(commitment[on_demand_spend])",
                     "\\€#,##0;-\\€#,##0", "ci-ondemand"),
        ],
    )

    # ─── Tabel 4: top_resources ───────────────────────────────────────
    top_resources = _table(
        short="top_resources",
        entity="mart_uc12_focus_top_resources",
        columns=[
            _col("billing_month", "dateTime", "datetime2",
                 format_str="yyyy-mm", tag_prefix="tr"),
            _col("provider", "string", "varchar(8000)", tag_prefix="tr"),
            _col("resource_id", "string", "varchar(8000)", tag_prefix="tr"),
            _col("resource_name", "string", "varchar(8000)", tag_prefix="tr"),
            _col("resource_type", "string", "varchar(8000)", tag_prefix="tr"),
            _col("service_name", "string", "varchar(8000)", tag_prefix="tr"),
            _col("service_category", "string", "varchar(8000)", tag_prefix="tr"),
            _col("region", "string", "varchar(8000)", tag_prefix="tr"),
            _col("application", "string", "varchar(8000)", tag_prefix="tr"),
            _col("environment", "string", "varchar(8000)", tag_prefix="tr"),
            _col("cost_center", "string", "varchar(8000)", tag_prefix="tr"),
            _col("sub_account_name", "string", "varchar(8000)", tag_prefix="tr"),
            _col("billing_currency", "string", "varchar(8000)", tag_prefix="tr"),
            _col("effective_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="tr"),
            _col("billed_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="tr"),
            _col("usage_quantity", "double", "float", summarize="sum",
                 format_str="#,##0.0000", tag_prefix="tr"),
            _col("usage_unit", "string", "varchar(8000)", tag_prefix="tr"),
            _col("n_charges", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="tr"),
            _col("rank_in_month", "int64", "bigint", summarize="none",
                 format_str="0", tag_prefix="tr"),
        ],
        measures=[
            _measure("Resource Cost",
                     "SUM(top_resources[effective_cost])",
                     "\\€#,##0;-\\€#,##0", "tr-cost"),
        ],
    )

    # ─── Tabel 5: savings ─────────────────────────────────────────────
    savings = _table(
        short="savings",
        entity="mart_uc12_focus_savings",
        columns=[
            _col("billing_month", "dateTime", "datetime2",
                 format_str="yyyy-mm", tag_prefix="sv"),
            _col("provider", "string", "varchar(8000)", tag_prefix="sv"),
            _col("pricing_category", "string", "varchar(8000)", tag_prefix="sv"),
            _col("service_category", "string", "varchar(8000)", tag_prefix="sv"),
            _col("charge_category", "string", "varchar(8000)", tag_prefix="sv"),
            _col("billing_currency", "string", "varchar(8000)", tag_prefix="sv"),
            _col("list_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sv"),
            _col("effective_cost", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sv"),
            _col("savings_amount", "double", "float", summarize="sum",
                 format_str="\\€#,##0.00;-\\€#,##0.00", tag_prefix="sv"),
            _col("savings_pct", "double", "float", summarize="none",
                 format_str="0.0%", tag_prefix="sv"),
            _col("n_charges", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="sv"),
            _col("n_resources", "int64", "bigint", summarize="sum",
                 format_str="#,##0", tag_prefix="sv"),
        ],
        measures=[
            _measure("Savings Total",
                     "SUM(savings[savings_amount])",
                     "\\€#,##0;-\\€#,##0", "sv-total"),
            _measure("Savings Pct",
                     "DIVIDE(SUM(savings[savings_amount]), "
                     "SUM(savings[list_cost]))",
                     "0.0%", "sv-pct"),
        ],
    )

    return {
        "compatibilityLevel": 1604,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "discourageImplicitMeasures": False,
            "expressions": [
                {
                    "name": "DatabaseQuery",
                    "kind": "m",
                    "expression": [
                        "let",
                        f"    database = Sql.Database(\"{SQL_HOST}\", \"{LAKEHOUSE_NAME}\")",
                        "in",
                        "    database",
                    ],
                    "lineageTag": "db-query-uc12",
                }
            ],
            "sourceQueryCulture": "en-US",
            "tables": [
                spend_monthly,
                service_breakdown,
                commitment,
                top_resources,
                savings,
            ],
            "relationships": [],
            "annotations": [
                {"name": "PBI_QueryOrder", "value": "[\"DatabaseQuery\"]"},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "1"},
                {"name": "PBI_ProTooling", "value": "[\"DevMode\"]"},
            ],
        },
    }


def write_semantic_model() -> None:
    SM_DIR.mkdir(parents=True, exist_ok=True)
    (SM_DIR / "definition.pbism").write_text(
        json.dumps(
            {
                "version": "4.0",
                "settings": {},
            },
            indent=2,
        )
    )
    (SM_DIR / "model.bim").write_text(json.dumps(build_model_bim(), indent=2))


# ═══════════════════════════════════════════════════════════════════════
# Report — PBIR tree
# ═══════════════════════════════════════════════════════════════════════

def measure_proj(entity: str, prop: str) -> dict:
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


def column_proj(entity: str, prop: str) -> dict:
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


def visual(
    name: str,
    x: int, y: int, w: int, h: int,
    visual_type: str,
    query_state: dict,
    title: str | None = None,
) -> dict:
    v: dict = {
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
            "title": [
                {
                    "properties": {
                        "text": {"expr": {"Literal": {"Value": f"'{title}'"}}}
                    }
                }
            ]
        }
    return v


def all_visuals() -> list[dict]:
    """De 12 visuals in 5 rijen, dezelfde grid als de UC-12 Superset-dashboard."""
    out: list[dict] = []

    # ─── Rij 1 — KPI cards (y=16, h=120) ──────────────────────────────
    out.append(visual(
        "v01_kpi_effective", 16, 16, 308, 120, "cardVisual",
        {"Data": {"projections": [measure_proj("spend_monthly", "Effective Cost Total")]}},
        title="Effective cost",
    ))
    out.append(visual(
        "v02_kpi_list", 332, 16, 308, 120, "cardVisual",
        {"Data": {"projections": [measure_proj("spend_monthly", "List Cost Total")]}},
        title="List cost",
    ))
    out.append(visual(
        "v03_kpi_savings", 648, 16, 308, 120, "cardVisual",
        {"Data": {"projections": [measure_proj("savings", "Savings Total")]}},
        title="Total savings",
    ))
    out.append(visual(
        "v04_kpi_coverage", 964, 16, 300, 120, "cardVisual",
        {"Data": {"projections": [measure_proj("commitment", "Avg Commitment Coverage")]}},
        title="Avg commitment coverage %",
    ))

    # ─── Rij 2 — Trends (y=144, h=240) ────────────────────────────────
    out.append(visual(
        "v05_line_spend_per_provider", 16, 144, 624, 240, "lineChart",
        {
            "Category": {"projections": [column_proj("spend_monthly", "billing_month")]},
            "Y":        {"projections": [measure_proj("spend_monthly", "Effective Cost Total")]},
            "Series":   {"projections": [column_proj("spend_monthly", "provider")]},
        },
        title="Effective cost per maand × provider",
    ))
    out.append(visual(
        "v06_line_coverage_per_svc", 648, 144, 616, 240, "lineChart",
        {
            "Category": {"projections": [column_proj("commitment", "billing_month")]},
            "Y":        {"projections": [measure_proj("commitment", "Avg Commitment Coverage")]},
            "Series":   {"projections": [column_proj("commitment", "service_category")]},
        },
        title="Commitment coverage % per maand × service-categorie",
    ))

    # ─── Rij 3 — Breakdowns (y=400, h=240) ────────────────────────────
    out.append(visual(
        "v07_pie_per_svc_category", 16, 400, 413, 240, "donutChart",
        {
            "Category": {"projections": [column_proj("service_breakdown", "service_category")]},
            "Y":        {"projections": [measure_proj("service_breakdown", "Service Spend")]},
        },
        title="Spend per service-categorie",
    ))
    out.append(visual(
        "v08_pie_per_region", 437, 400, 413, 240, "donutChart",
        {
            "Category": {"projections": [column_proj("service_breakdown", "region")]},
            "Y":        {"projections": [measure_proj("service_breakdown", "Service Spend")]},
        },
        title="Spend per regio",
    ))
    out.append(visual(
        "v09_pie_per_environment", 858, 400, 406, 240, "donutChart",
        {
            "Category": {"projections": [column_proj("service_breakdown", "environment")]},
            "Y":        {"projections": [measure_proj("service_breakdown", "Service Spend")]},
        },
        title="Spend per environment",
    ))

    # ─── Rij 4 — Drill-downs (y=656, h=220) ───────────────────────────
    out.append(visual(
        "v10_bar_top_services", 16, 656, 624, 220, "clusteredBarChart",
        {
            "Category": {"projections": [column_proj("service_breakdown", "service_name")]},
            "Y":        {"projections": [measure_proj("service_breakdown", "Service Spend")]},
        },
        title="Top services op effective cost",
    ))
    out.append(visual(
        "v11_bar_per_application", 648, 656, 616, 220, "clusteredBarChart",
        {
            "Category": {"projections": [column_proj("service_breakdown", "application")]},
            "Y":        {"projections": [measure_proj("service_breakdown", "Service Spend")]},
        },
        title="Spend per applicatie (uit tags)",
    ))

    # ─── Rij 5 — Detail-tabel (y=892, h=132) ──────────────────────────
    out.append(visual(
        "v12_tbl_top_resources", 16, 892, 1248, 132, "tableEx",
        {
            "Values": {
                "projections": [
                    column_proj("top_resources", "resource_id"),
                    column_proj("top_resources", "service_name"),
                    column_proj("top_resources", "region"),
                    column_proj("top_resources", "application"),
                    measure_proj("top_resources", "Resource Cost"),
                ]
            }
        },
        title="Top-resources op effective cost",
    ))

    return out


# ─── PBIR root files ────────────────────────────────────────────────────
def report_pbir(semantic_model_id: str) -> dict:
    return {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definitionProperties/2.0.0/schema.json"
        ),
        "version": "4.0",
        "datasetReference": {
            "byConnection": {
                "connectionString": f"semanticmodelid={semantic_model_id}"
            }
        },
    }


def report_json() -> dict:
    return {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/report/3.0.0/schema.json"
        ),
        "themeCollection": {
            "baseTheme": {
                "name": "CY24SU10",
                "type": "SharedResources",
                "reportVersionAtImport": {
                    "visual": "1.8.97",
                    "report": "2.0.97",
                    "page": "1.3.97",
                },
            }
        },
        "settings": {
            "useStylableVisualContainerHeader": True,
            "useEnhancedTooltips": True,
            "defaultDrillFilterOtherVisuals": True,
        },
    }


def version_json() -> dict:
    return {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/versionMetadata/1.0.0/schema.json"
        ),
        "version": "2.0.0",
    }


def pages_json() -> dict:
    return {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/pagesMetadata/1.0.0/schema.json"
        ),
        "pageOrder": [PAGE_ID],
        "activePageName": PAGE_ID,
    }


def page_json() -> dict:
    return {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/page/2.0.0/schema.json"
        ),
        "name": PAGE_ID,
        "displayName": "UC-12 FinOps (FOCUS)",
        "displayOption": "FitToPage",
        "height": PAGE_H,
        "width": PAGE_W,
        "pageBinding": {
            "name": "uc12binding",
            "type": "Default",
            "parameters": [],
            "acceptsFilterContext": "None",
        },
    }


def write_report(semantic_model_id: str) -> None:
    # Schoonschip — anders blijven oude visuals achter na renames.
    if RP_DIR.exists():
        for p in sorted(RP_DIR.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
    RP_DIR.mkdir(parents=True, exist_ok=True)

    (RP_DIR / "definition.pbir").write_text(
        json.dumps(report_pbir(semantic_model_id), indent=2)
    )
    defin = RP_DIR / "definition"
    defin.mkdir(exist_ok=True)
    (defin / "version.json").write_text(json.dumps(version_json(), indent=2))
    (defin / "report.json").write_text(json.dumps(report_json(), indent=2))

    pages = defin / "pages"
    pages.mkdir(exist_ok=True)
    (pages / "pages.json").write_text(json.dumps(pages_json(), indent=2))

    page = pages / PAGE_ID
    page.mkdir(exist_ok=True)
    (page / "page.json").write_text(json.dumps(page_json(), indent=2))

    visuals = page / "visuals"
    visuals.mkdir(exist_ok=True)
    for v in all_visuals():
        vdir = visuals / v["name"]
        vdir.mkdir(exist_ok=True)
        (vdir / "visual.json").write_text(json.dumps(v, indent=2))


# ═══════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════

def _resolve_semantic_model_id_or_placeholder(arg: str | None) -> str:
    """Probeer een echt SemanticModel-ID op te halen; anders gebruik
    een placeholder zodat de PBIR-bestanden uberhaupt geschreven worden
    (eerste upload past 'm aan via byPath bind achteraf)."""
    if arg:
        return arg
    if not os.environ.get("FABRIC_TENANT_ID"):
        return "00000000-0000-0000-0000-000000000000"
    sys.path.insert(0, str(REPO_ROOT / "platform" / "11-airflow" / "include"))
    from fabric_helpers import get_token, list_items  # noqa: E402
    for m in list_items(get_token(), "SemanticModel"):
        if m["displayName"] == "uc12_focus_finops":
            return m["id"]
    return "00000000-0000-0000-0000-000000000000"


def main() -> None:
    write_semantic_model()
    print(f"SemanticModel geschreven naar {SM_DIR}")

    sid = _resolve_semantic_model_id_or_placeholder(
        sys.argv[1] if len(sys.argv) > 1 else None
    )
    if sid == "00000000-0000-0000-0000-000000000000":
        print(
            "  → placeholder SemanticModel-ID gebruikt; upload-script vervangt "
            "deze automatisch na de eerste upload (run hierna opnieuw zodat "
            "byConnection.connectionString to the echte ID wijst)."
        )
    else:
        print(f"  → SemanticModel-ID: {sid}")

    write_report(sid)
    n_files = sum(1 for _ in OUT_DIR.rglob("*") if _.is_file())
    print(f"Report geschreven naar {RP_DIR}")
    print(f"Totaal: {n_files} files onder {OUT_DIR}")


if __name__ == "__main__":
    main()
