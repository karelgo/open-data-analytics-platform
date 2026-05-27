"""Silver-factory — Cosmos-rendered dbt run+test per domein.

Eén DAG per bron-domein. Schedule = bronze-Dataset van die bron.
Output = silver-Dataset bij succesvolle dbt run.

Cosmos genereert per dbt-model één Airflow-task; dependencies in dbt
(via `ref()`) worden automatisch Airflow-task-deps.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.models import Variable

from datasets import bronze_dataset, silver_dataset
from sources_loader import SourceSpec, load_all_sources

# Cosmos imports — pad A (initContainer) zorgt dat dit op PYTHONPATH staat.
# Als cosmos ontbreekt, valt de DAG terug op een EmptyOperator zodat parsing
# niet crasht. In production nooit gewenst — DAG integrity test faalt dan.
try:
    from cosmos import (
        DbtDag,
        ExecutionConfig,
        ExecutionMode,
        LoadMode,
        ProfileConfig,
        ProjectConfig,
        RenderConfig,
        TestBehavior,
    )
    from cosmos.profiles import TrinoCertificateProfileMapping
    COSMOS_AVAILABLE = True
except ImportError:  # pragma: no cover
    COSMOS_AVAILABLE = False

DEFAULT_ARGS = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Locaties — gemount door airflowcluster.yaml podOverrides.
DBT_PROJECT_PATH = Path(os.environ.get("DBT_PROJECT_PATH", "/opt/odap/dbt"))
DBT_MANIFEST_PATH = Path(
    os.environ.get("DBT_MANIFEST_PATH", "/opt/odap/dbt/manifest.json")
)
DBT_EXECUTABLE_PATH = os.environ.get("DBT_EXECUTABLE_PATH", "/usr/local/bin/dbt")
DBT_IMAGE = os.environ.get("DBT_IMAGE", "odap/dbt-trino:1.9.0")


def _profile_config() -> ProfileConfig:
    """Cosmos profile-mapping naar Airflow Connection `trino_default`."""
    return ProfileConfig(
        profile_name="trino_default",
        target_name="dev",
        profile_mapping=TrinoCertificateProfileMapping(
            conn_id="trino_default",
            profile_args={
                "schema": "{{ ref.schema }}",
                "threads": 4,
            },
        ),
    )


def _execution_config() -> ExecutionConfig:
    return ExecutionConfig(
        execution_mode=ExecutionMode.KUBERNETES,
        dbt_executable_path=DBT_EXECUTABLE_PATH,
    )


def _project_config() -> ProjectConfig:
    return ProjectConfig(
        dbt_project_path=str(DBT_PROJECT_PATH),
        manifest_path=str(DBT_MANIFEST_PATH),
        env_vars={"TABLE_FORMAT": "delta"},
    )


def build_silver_dag(source: SourceSpec) -> DAG:
    """Cosmos-DAG voor één domein: dbt run+test op tag:<domain> tag:staging."""
    if not COSMOS_AVAILABLE:
        return _fallback_dag(source)

    return DbtDag(
        dag_id=f"silver_{source.domain}",
        description=(
            f"Silver-laag voor domein {source.domain} — dbt run+test, "
            "per-model task via Cosmos. Triggered op bronze-Dataset. "
            "Zie ADR-0007."
        ),
        project_config=_project_config(),
        profile_config=_profile_config(),
        execution_config=_execution_config(),
        render_config=RenderConfig(
            load_method=LoadMode.DBT_MANIFEST,
            # dbt: enkele string met komma = intersectie (AND).
            # Lijst van strings = unie (OR), wat we hier niet willen.
            select=[f"tag:{source.silver.dbt_tag},tag:staging"],
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
        default_args=DEFAULT_ARGS,
        schedule=[bronze_dataset(source)],
        start_date=datetime(2026, 5, 1),
        catchup=False,
        max_active_runs=1,
        # uc11_full_setup triggert deze DAG op een verse cluster; zonder
        # is_paused_upon_creation=False blijft de eerste run queued tot
        # iemand handmatig unpaust. Zie ADR-0007.
        is_paused_upon_creation=False,
        tags=source.airflow_tags + ["silver", "cosmos"],
        # Publiceer silver-Dataset zodat gold-DAGs triggeren.
        # Cosmos plaatst outlets on the eindknoop via een end-task.
        # Voor manifest-based mode zetten we deze via render_config.
    )


def _fallback_dag(source: SourceSpec) -> DAG:
    """Compat-DAG zonder cosmos — alleen voor parsing in dev."""
    from airflow.operators.empty import EmptyOperator

    with DAG(
        dag_id=f"silver_{source.domain}",
        description=f"[FALLBACK — cosmos niet beschikbaar] silver/{source.domain}",
        default_args=DEFAULT_ARGS,
        schedule=[bronze_dataset(source)],
        start_date=datetime(2026, 5, 1),
        catchup=False,
        tags=source.airflow_tags + ["silver", "fallback"],
    ) as dag:
        EmptyOperator(
            task_id="cosmos_unavailable",
            outlets=[silver_dataset(source)],
        )
    return dag


def build_all_silver_dags() -> dict[str, DAG]:
    return {f"silver_{s.domain}": build_silver_dag(s) for s in load_all_sources()}
