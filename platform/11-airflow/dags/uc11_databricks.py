"""UC-11 — multi-platform demo: Databricks variant.

Draait een batch-only uc11 pijplijn tegen Databricks Unity Catalog. Geen
streaming bronze. Equivalent van uc11_fabric, maar dan tegen Databricks
compute en UC-managed Delta tabellen (catalog: `databricks`).

Tasks:
  1. databricks_seed_silver — POST /api/2.1/jobs/run-now op de uc11-pipeline
                              Job; wacht tot beide notebook-tasks (seed_bronze +
                              silver) klaar zijn. Schrijft naar
                              databricks.bronze.* en databricks.silver.*.
  2. databricks_dbt_gold    — KubernetesPodOperator: `dbt run --target
                              databricks_dev` met dbt-databricks. Bouwt
                              int_customer_journey_events + 2 marts uit het échte
                              dbt-project — zelfde SQL als Trino én Fabric
                              executeren (drie engines, één dbt-project).
  3. databricks_verify      — SQL-warehouse query: row-count > 0 op
                              databricks.gold.mart_uc11_journey_events.

Voorvereisten (in-cluster):
  - Kubernetes Secret 'uc11-multiplatform-creds' gemount als envFrom (heeft
    DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH, DATABRICKS_CATALOG,
    DATABRICKS_WAREHOUSE_ID).
  - Airflow Variable 'databricks_uc11_job_id' met de Job-ID (alleen
    seed_bronze + silver tasks; dbt_gold task is verwijderd uit de Job —
    die draait nu via deze DAG's KPO).
  - dbt-databricks zit in de odap/dbt-trino:1.9.0 image (zelfde image
    als fabric_dbt_gold gebruikt).

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client.models import V1EnvFromSource, V1SecretEnvSource

from databricks_helpers import (
    DATABRICKS_CATALOG,
    execute_sql,
    run_job,
    wait_for_run,
)

DEFAULT_ARGS = {
    "owner": "data-steward",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
}

GOLD_TABLE_FQN = f"{DATABRICKS_CATALOG}.gold.mart_uc11_journey_events"

# Zelfde image als fabric_dbt_gold — bevat dbt-trino + dbt-fabricspark + dbt-databricks.
# /opt/odap/dbt/ heeft het dbt-project; /root/.dbt/profiles.yml heeft alle drie de
# targets (dev=trino, fabric_dev, databricks_dev) met env_var() substitution.
DBT_IMAGE = "odap/dbt-trino:1.9.0"
DBT_SECRET = "uc11-multiplatform-creds"

# dbt-databricks run-script voor de KPO.
#
# Twee dingen die we adhoc fixen omdat de odap/dbt-trino:1.9.0 image
# (gedeeld met fabric_dbt_gold) initiëel alleen dbt-trino + dbt-fabricspark
# heeft:
#   1. `pip install dbt-databricks~=1.11.0` — komt mee in pip-cache; <15s
#   2. Een tijdelijke profiles.yml met databricks_dev target naar /tmp/profiles
#      die de DATABRICKS_* env-vars uit het Secret leest.
# Volgende image-build kan dit incorporeren — dan vervalt de pip-install
# stap en kan profiles.yml gewoon de embedded versie gebruiken.
DBT_RUN_SCRIPT = r"""
set -euo pipefail
cd /opt/odap/dbt

echo '=== install dbt-databricks adapter (niet in base image) ==='
pip install --quiet --disable-pip-version-check 'dbt-databricks~=1.11.0'

echo '=== schrijf adhoc profiles.yml met databricks_dev target ==='
mkdir -p /tmp/profiles
cat > /tmp/profiles/profiles.yml <<EOF
trino_default:
  target: databricks_dev
  outputs:
    databricks_dev:
      type: databricks
      host: ${DATABRICKS_HOST}
      http_path: ${DATABRICKS_HTTP_PATH}
      token: ${DATABRICKS_TOKEN}
      catalog: ${DATABRICKS_CATALOG}
      schema: dbt_default
      threads: 4
      connect_retries: 3
      connect_timeout: 60
EOF

echo '=== dbt debug ==='
dbt debug --profiles-dir /tmp/profiles --target databricks_dev || echo '(debug-warning negeerd)'

echo '=== dbt run ==='
dbt run --no-partial-parse --profiles-dir /tmp/profiles --target databricks_dev \
  --select int_customer_journey_events+
"""


def _trigger_seed_silver(**_) -> None:
    """Trigger Databricks Job (seed_bronze + silver tasks) en wacht op completion."""
    job_id = int(Variable.get("databricks_uc11_job_id"))
    run_id = run_job(job_id)
    print(f"Databricks run_id={run_id} gestart voor job {job_id}")
    wait_for_run(run_id, timeout_s=3600, poll_interval_s=20)


def _verify_gold_mart(**_) -> None:
    """SQL-warehouse query op de gold-mart: row-count > 0."""
    result = execute_sql(f"SELECT COUNT(*) AS n FROM {GOLD_TABLE_FQN}")
    data = result.get("result", {}).get("data_array") or []
    if not data:
        raise RuntimeError(f"Geen data terug van {GOLD_TABLE_FQN}: {result}")
    n = int(data[0][0])
    if n == 0:
        raise RuntimeError(f"{GOLD_TABLE_FQN} heeft 0 rijen")
    print(f"{GOLD_TABLE_FQN}: {n} rijen — OK")


with DAG(
    dag_id="uc11_databricks",
    description="UC-11 multi-platform demo — Databricks variant",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 5, 19),
    schedule=None,
    catchup=False,
    tags=["uc11", "multi-platform", "databricks"],
) as dag:
    seed_silver = PythonOperator(
        task_id="databricks_seed_silver",
        python_callable=_trigger_seed_silver,
    )
    # Vervangt het oude uc11_dbt_gold notebook (inline Spark-SQL in Databricks
    # workspace). Draait nu het échte dbt-project tegen Databricks SQL warehouse
    # via dbt-databricks — zelfde SQL als Trino én Fabric executeren.
    # Symmetrisch met fabric_dbt_gold in uc11_fabric DAG.
    gold = KubernetesPodOperator(
        task_id="databricks_dbt_gold",
        namespace="odap-platform",
        image=DBT_IMAGE,
        cmds=["bash", "-c"],
        arguments=[DBT_RUN_SCRIPT],
        env_from=[
            V1EnvFromSource(secret_ref=V1SecretEnvSource(name=DBT_SECRET)),
        ],
        # Geen request/limit (zelfde reden als fabric_dbt_gold) — dbt-core piek
        # bij startup > SMALL_POD_RESOURCES.
        container_resources=None,
        # SQL-warehouse warm start typisch <30s; geen Livy cold-start nodig.
        startup_timeout_seconds=180,
        on_finish_action="delete_succeeded_pod",
        get_logs=True,
    )
    verify = PythonOperator(
        task_id="databricks_verify",
        python_callable=_verify_gold_mart,
    )

    seed_silver >> gold >> verify
