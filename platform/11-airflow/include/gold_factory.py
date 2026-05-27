"""Gold-factory — Cosmos-rendered dbt run+test per use-case.

Eén DAG per UC. Schedule = silver-Datasets van álle bronnen die deze UC
gebruikt (uit YAML-registry, veld `used_by_use_cases`).

Cosmos selecteert via `tag:<uc>` zodat alle marts (en hun intermediate-deps)
in volgorde worden gerund.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG

from datasets import silver_datasets_for_use_case
from silver_factory import (
    COSMOS_AVAILABLE,
    DBT_IMAGE,
    DEFAULT_ARGS,
    _execution_config,
    _profile_config,
    _project_config,
)

if COSMOS_AVAILABLE:
    from cosmos import DbtDag, LoadMode, RenderConfig, TestBehavior


# Welke UCs hebben actieve marts? (Marts die leeg zijn skippen we voorlopig.)
ACTIVE_USE_CASES: list[dict] = [
    {"id": "uc01", "name": "wia_funnel", "owner": "divisie_ag",
     "description": "WIA Funnel — sturingsinformatie."},
    {"id": "uc04", "name": "tw_eligibility", "owner": "divisie_uitkeren",
     "description": "Toeslagenwet eligibility-check."},
    {"id": "uc05", "name": "client_360", "owner": "divisie_customer interaction",
     "description": "Cliënt 360 — gepseudonimiseerd."},
    {"id": "uc06", "name": "cost forecast", "owner": "divisie_fez",
     "description": "Claim payoutslast 5-jaar prognose + scenarios."},
    {"id": "uc07", "name": "dq_polisadm", "owner": "data_office",
     "description": "Data quality dagrapport polisadministratie."},
    {"id": "uc09", "name": "reint_effect", "owner": "divisie_ag",
     "description": "Reintegration-effect (sandbox, gepseudonimiseerd)."},
    {"id": "uc11", "name": "customer journey", "owner": "divisie_customer interaction",
     "description": "Integrale Customer journey — event-stream + fase-reconstructie."},
    {"id": "uc12", "name": "focus_finops", "owner": "divisie_finance",
     "description": "Cloud-cost FinOps (FOCUS) — spend, savings, commitment-utilization."},
    {"id": "uc_customer_satisfaction", "name": "customer_satisfaction", "owner": "divisie_customer interaction",
     "description": "Klanttevredenheid per kanaal × maand (CSV-batch demo)."},
]


def build_gold_dag(uc: dict) -> DAG:
    triggers = silver_datasets_for_use_case(uc["id"])
    if not triggers:
        return _no_triggers_dag(uc)
    if not COSMOS_AVAILABLE:
        return _fallback_dag(uc, triggers)

    return DbtDag(
        dag_id=f"gold_{uc['id']}_{uc['name']}",
        description=(
            f"{uc['description']} — gold-marts via Cosmos. "
            f"Triggered door {len(triggers)} silver-Datasets. Zie ADR-0007."
        ),
        project_config=_project_config(),
        profile_config=_profile_config(),
        execution_config=_execution_config(),
        render_config=RenderConfig(
            load_method=LoadMode.DBT_MANIFEST,
            select=[f"tag:{uc['id']}"],
            test_behavior=TestBehavior.AFTER_EACH,
        ),
        operator_args={
            "image": DBT_IMAGE,
            "namespace": "odap-platform",
            "is_delete_operator_pod": True,
            "get_logs": True,
            "container_resources": {
                "requests": {"cpu": "100m", "memory": "256Mi"},
                "limits": {"cpu": "500m", "memory": "1Gi"},
            },
        },
        default_args={**DEFAULT_ARGS, "owner": uc["owner"]},
        schedule=triggers,
        start_date=datetime(2026, 5, 1),
        catchup=False,
        max_active_runs=1,
        # uc11_full_setup triggert UC-11 op een verse cluster; alle gold-DAGs
        # mogen onpaused starten — gold runt alleen als hun silver-deps
        # binnenkomen, dus geen automatische scheduler-runs op cold start.
        is_paused_upon_creation=False,
        tags=["demo", "gold", "cosmos", f"usecase:{uc['id']}", f"owner:{uc['owner']}"],
    )


def _no_triggers_dag(uc: dict) -> DAG:
    """UC zonder bekende silver-deps — DAG bestaat maar runt nooit auto."""
    from airflow.operators.empty import EmptyOperator

    with DAG(
        dag_id=f"gold_{uc['id']}_{uc['name']}",
        description=f"[INACTIEF — geen silver-deps gevonden] {uc['description']}",
        default_args=DEFAULT_ARGS,
        schedule=None,
        start_date=datetime(2026, 5, 1),
        catchup=False,
        tags=["demo", "gold", "inactive", f"usecase:{uc['id']}"],
    ) as dag:
        EmptyOperator(task_id="no_triggers_configured")
    return dag


def _fallback_dag(uc: dict, triggers) -> DAG:
    """Compat-DAG zonder cosmos."""
    from airflow.operators.empty import EmptyOperator

    with DAG(
        dag_id=f"gold_{uc['id']}_{uc['name']}",
        description=f"[FALLBACK — cosmos niet beschikbaar] {uc['description']}",
        default_args={**DEFAULT_ARGS, "owner": uc["owner"]},
        schedule=triggers,
        start_date=datetime(2026, 5, 1),
        catchup=False,
        tags=["demo", "gold", "fallback", f"usecase:{uc['id']}"],
    ) as dag:
        EmptyOperator(task_id="cosmos_unavailable")
    return dag


def build_all_gold_dags() -> dict[str, DAG]:
    return {
        f"gold_{uc['id']}_{uc['name']}": build_gold_dag(uc)
        for uc in ACTIVE_USE_CASES
    }
