"""UC-11 — multi-platform demo: Microsoft Fabric variant.

Draait een batch-only uc11 pijplijn tegen een Fabric Lakehouse op OneLake.
Geen streaming bronze (zie ADR over scope-versimpeling). Equivalent van
uc11_full_setup, maar dan met Fabric Spark in plaats van Stackable Spark.

Tasks:
  1. fabric_bootstrap   — verifieer workspace + Lakehouse, resolve notebook-IDs
  2. fabric_seed_bronze — trigger 'uc11_seed_bronze' notebook (synthetic data)
  3. fabric_silver      — trigger 'uc11_silver' notebook (per-domein staging)
  4. fabric_dbt_gold    — KubernetesPodOperator: `dbt run --target fabric_dev`
                          met dbt-fabricspark; runt int_customer_journey_events +
                          2 marts uit het échte dbt-project (zelfde SQL als
                          op Trino — portabiliteits-demo).
  5. fabric_verify      — controleer dat de gold-mart in het Lakehouse staat

Voorvereisten (eerste deploy):
  - Service Principal met workspace-contributor op de Fabric workspace
    (env-vars FABRIC_*; in-cluster via Kubernetes Secret 'uc11-multiplatform-creds').
    Aanmaken: `kubectl create secret generic uc11-multiplatform-creds
              --namespace odap-platform
              --from-env-file=secrets/local/uc11-multiplatform.env`
  - Twee notebooks in de workspace met displayName uit NOTEBOOK_NAMES.
    Eerste bootstrap stelt vast welke ontbreken — upload via Fabric UI of REST.
    `uc11_dbt_gold.ipynb` is vervangen door fabric_dbt_gold KPO; notebook
    bestaat nog als doc-stub maar wordt niet meer getriggered.
  - dbt-fabricspark zit in de odap/dbt-trino:1.9.0 image (pip-install
    in infrastructure/airflow/dbt/Dockerfile).
  - Optioneel: Airflow Variable 'fabric_uc11_notebooks' (JSON dict
    {displayName: itemId}) om automatische resolution te overrulen.

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client.models import V1EnvFromSource, V1SecretEnvSource

from fabric_helpers import (
    FABRIC_ENDPOINT,
    FABRIC_LAKEHOUSE_ID,
    FABRIC_WORKSPACE_ID,
    get_token,
    list_items,
    list_lakehouse_tables,
    trigger_notebook,
    wait_for_operation,
)

DEFAULT_ARGS = {
    "owner": "data-steward",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
}

# Notebooks die we nog wél via REST triggeren. uc11_dbt_gold is bewust
# weggehaald: gold-marts komen nu via dbt-fabricspark (fabric_dbt_gold KPO).
NOTEBOOK_NAMES = ("uc11_seed_bronze", "uc11_silver")
GOLD_MART = "mart_uc11_journey_events"

# Image die zowel dbt-trino als dbt-fabricspark heeft (zie
# infrastructure/airflow/dbt/Dockerfile). Bevat het hele dbt-project op
# /opt/odap/dbt/ en profiles.yml op /root/.dbt/profiles.yml met `fabric_dev`
# target die env-vars uit het Secret hieronder leest.
DBT_IMAGE = "odap/dbt-trino:1.9.0"
DBT_SECRET = "uc11-multiplatform-creds"


def _resolve_notebook_ids(**_) -> dict[str, str]:
    """Vind notebook-IDs by displayName; push naar XCom.

    Volgorde: eerst Airflow Variable 'fabric_uc11_notebooks' (JSON override),
    daarna workspace-enumeratie. Faalt expliciet als een notebook ontbreekt
    zodat de DAG niet stilletjes door schiet naar een lege run.
    """
    try:
        overrides = json.loads(Variable.get("fabric_uc11_notebooks"))
    except Exception:
        overrides = {}

    token = get_token()
    by_name = {n["displayName"]: n["id"] for n in list_items(token, "Notebook")}

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for name in NOTEBOOK_NAMES:
        if name in overrides:
            resolved[name] = overrides[name]
        elif name in by_name:
            resolved[name] = by_name[name]
        else:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"Ontbrekende Fabric-notebooks: {missing}. Upload naar workspace "
            f"{FABRIC_WORKSPACE_ID} of zet Airflow Variable "
            "'fabric_uc11_notebooks'."
        )
    return resolved


def _run_notebook(notebook_key: str, **ctx) -> None:
    notebooks: dict[str, str] = ctx["ti"].xcom_pull(task_ids="fabric_bootstrap")
    if not notebooks or notebook_key not in notebooks:
        raise RuntimeError(
            f"Notebook '{notebook_key}' niet beschikbaar in bootstrap-XCom: {notebooks}"
        )
    token = get_token()
    op_url = trigger_notebook(
        token,
        notebooks[notebook_key],
        parameters={
            "workspace_id": FABRIC_WORKSPACE_ID,
            "lakehouse_id": FABRIC_LAKEHOUSE_ID,
        },
    )
    wait_for_operation(token, op_url)


def _verify_gold_mart(**_) -> None:
    """Sanity-check: gold-mart staat in het Lakehouse.

    De Fabric tables-endpoint kan een sync-delay hebben t.o.v. een verse
    notebook-write (typisch <60s). We doen drie pogingen met 30s pauze.
    """
    import time

    token = get_token()
    for attempt in range(3):
        tables = list_lakehouse_tables(token)
        if GOLD_MART in tables:
            return
        if attempt < 2:
            time.sleep(30)
    raise RuntimeError(
        f"'{GOLD_MART}' niet zichtbaar in lakehouse {FABRIC_LAKEHOUSE_ID} na sync-wait. "
        f"Endpoint: {FABRIC_ENDPOINT}. Gevonden tabellen: {tables}"
    )


# dbt-fabricspark run-script voor de KPO. Werkdir is /opt/odap/dbt (zie image);
# profiles.yml zit op /root/.dbt/profiles.yml. `--no-partial-parse` voorkomt
# stale manifest-issues in een verse pod. `--select int_customer_journey_events+`
# bouwt alleen wat we voor Fabric nodig hebben — staging blijft op Trino.
DBT_RUN_SCRIPT = (
    "set -euo pipefail\n"
    "cd /opt/odap/dbt\n"
    "echo '=== dbt debug ==='\n"
    "dbt debug --target fabric_dev || echo '(debug-warning negeerd; ga door naar run)'\n"
    "echo '=== dbt run ==='\n"
    "dbt run --no-partial-parse --target fabric_dev "
    "--select int_customer_journey_events+\n"
)


with DAG(
    dag_id="uc11_fabric",
    description="UC-11 multi-platform demo — Microsoft Fabric variant",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 5, 18),
    schedule=None,
    catchup=False,
    tags=["uc11", "multi-platform", "fabric"],
) as dag:
    bootstrap = PythonOperator(
        task_id="fabric_bootstrap",
        python_callable=_resolve_notebook_ids,
    )
    seed = PythonOperator(
        task_id="fabric_seed_bronze",
        python_callable=_run_notebook,
        op_kwargs={"notebook_key": "uc11_seed_bronze"},
    )
    silver = PythonOperator(
        task_id="fabric_silver",
        python_callable=_run_notebook,
        op_kwargs={"notebook_key": "uc11_silver"},
    )
    # Vervangt het oude uc11_dbt_gold notebook (inline Spark-SQL). Draait
    # nu het échte dbt-project tegen Fabric Spark via Livy — zelfde SQL
    # als Trino executeert, demonstreert dbt-portabiliteit.
    gold = KubernetesPodOperator(
        task_id="fabric_dbt_gold",
        namespace="odap-platform",
        image=DBT_IMAGE,
        cmds=["bash", "-c"],
        arguments=[DBT_RUN_SCRIPT],
        env_from=[
            V1EnvFromSource(secret_ref=V1SecretEnvSource(name=DBT_SECRET)),
        ],
        # Geen request/limit: dbt-core + Spark-client + Livy-session
        # piekt > de 256Mi van SMALL_POD_RESOURCES bij startup wat OOM
        # geeft binnen ~3s (zelfde script werkt prima in een onbegrensd pod).
        container_resources=None,
        # Livy-session warmup (cold start) duurt 50-60s; default 120s timeout
        # is voldoende maar ruim genomen voor extra speling.
        startup_timeout_seconds=300,
        # Faalde pods 30 min houden voor log-inspectie; succesvolle pods
        # direct opruimen om de cluster netjes te houden.
        on_finish_action="delete_succeeded_pod",
        get_logs=True,
    )
    verify = PythonOperator(
        task_id="fabric_verify",
        python_callable=_verify_gold_mart,
    )

    bootstrap >> seed >> silver >> gold >> verify
