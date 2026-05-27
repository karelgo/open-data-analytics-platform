"""transform_wia_spark — Spark-versie van het silver+gold-pad voor WIA.

⚠️  GEBLOKKEERD door Stackable Airflow 3.0.6 infra-bug ⚠️
   Het Airflow `/execution/` API-endpoint dat task-pods nodig hebben om hun
   TaskInstance te registreren bestaat NIET op deze SDP-release. Geen enkele
   DAG runt sinds 2026-05-18.

   Diagnose & workaround zijn vastgelegd in
   memory/feedback_stackable_airflow3_execution_api_missing.md.

   WORKAROUND: gebruik `make wia-spark-demo` (scripts/wia-spark-demo.sh) —
   die doet hetzelfde werk als deze DAG maar zonder Airflow-orchestratie.

   Deze DAG blijft staan zodat hij direct werkt zodra de infra-bug
   opgelost is (geen code-wijziging nodig in de DAG).

---

PARALLEL aan het bestaande dbt-pad (silver_wia + gold_uc01_claims_funnel via
transform_silver_per_domain / transform_gold_per_usecase). Schrijft naar
aparte HMS-schemas zodat dbt-tabellen onaangeraakt blijven:

  dbt:    silver.claims.stg_claim_application         gold.uc01_claims_funnel.mart_*
  spark:  silver.wia_spark.aanvraag           gold.uc01_wia_spark.funnel_daily

Het werk gebeurt in Stackable SparkApplications. Deze DAG creëert per run
een unieke SparkApplication (uniek genaamd) door een template uit de
airflow-jobs ConfigMap te substitueren met sed, applied via kubectl, en
polled tot status.phase ∈ {Succeeded, Failed}.

BENODIGD: Airflow's ServiceAccount moet SparkApplications mogen
create/get/delete in odap-platform — zie platform/11-airflow/rbac-spark.yaml.

Schedule:
  None (alleen handmatige trigger of via TriggerDagRunOperator). Reden:
  bronze.claims.application wordt nu handmatig geseed (zie seed-bronze-claims
  SparkApplication), niet door een streaming-DAG. Voor productie: vervang
  door schedule=[bronze_wia_dataset].

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.datasets import Dataset
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client.models import (
    V1ConfigMapVolumeSource,
    V1EnvVar,
    V1ResourceRequirements,
    V1Volume,
    V1VolumeMount,
)

# kubectl image — bevat `kubectl` + standaard busybox-shell (sed, sleep).
# Pin minor-version i.p.v. latest voor reproduceerbaarheid.
KUBECTL_IMAGE = "bitnami/kubectl:1.30"

JOBS_CM = "airflow-jobs"
JOBS_MOUNT = "/opt/odap/airflow/jobs"

NAMESPACE = "odap-platform"

# Datasets — downstream DAGs kunnen hierop schedulen.
SILVER_DATASET = Dataset("odap://silver/wia_spark/aanvraag")
GOLD_DATASET = Dataset("odap://gold/uc01_wia_spark/funnel_daily")

DEFAULT_ARGS = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
}

# Heel kleine pod — doet niets dan kubectl-calls.
KUBECTL_POD_RESOURCES = V1ResourceRequirements(
    requests={"cpu": "50m", "memory": "64Mi"},
    limits={"cpu": "200m", "memory": "128Mi"},
)


def _run_spark_app_cmd(template_filename: str, name_prefix: str) -> list[str]:
    """Bash-script dat de SparkApplication apply + status pollt.

    - Substitueert ${RUN_ID} in de template (sed, geen envsubst-dep)
    - Applied via kubectl
    - Polled `.status.phase` elke 10s, max 25 min
    - Print driver-logs op failure
    - Verwijdert de SparkApplication CR aan het einde (succes-pad);
      bij failure laat 'em staan voor postmortem
    """
    # Note: enkele quotes rond de bash-string; alle ${VARS} worden door bash
    # zelf ge-expand (NIET door Airflow Jinja). Jinja-vars worden los
    # gepasseerd via env_vars en pop up als $VAR in de shell.
    return [
        f"""
set -euo pipefail

RUN_ID="${{AIRFLOW_RUN_ID}}"
NAME="{name_prefix}-${{RUN_ID}}"
TEMPLATE="{JOBS_MOUNT}/{template_filename}"
TIMEOUT_LOOPS=150  # 150 × 10s = 25 min

echo "==> Apply SparkApplication ${{NAME}}"
sed "s|\\${{RUN_ID}}|${{RUN_ID}}|g" "${{TEMPLATE}}" | kubectl apply -f -

echo "==> Poll status (max 25 min)"
for i in $(seq 1 ${{TIMEOUT_LOOPS}}); do
  phase=$(kubectl get sparkapplication "${{NAME}}" -n {NAMESPACE} \\
    -o jsonpath='{{.status.phase}}' 2>/dev/null || echo "Unknown")
  printf '  [poll %3d] phase=%s\\n' "${{i}}" "${{phase}}"
  case "${{phase}}" in
    Succeeded)
      echo "==> ${{NAME}} succeeded — cleaning up CR"
      kubectl delete sparkapplication "${{NAME}}" -n {NAMESPACE} --wait=false || true
      exit 0
      ;;
    Failed)
      echo "==> ${{NAME}} FAILED — driver logs:"
      driver_pod=$(kubectl get pods -n {NAMESPACE} \\
        -l spark-app-name="${{NAME}}",spark-role=driver \\
        -o jsonpath='{{.items[0].metadata.name}}' 2>/dev/null || echo "")
      if [ -n "${{driver_pod}}" ]; then
        kubectl logs "${{driver_pod}}" -n {NAMESPACE} --tail=200 || true
      else
        echo "  (geen driver-pod gevonden)"
      fi
      echo "==> CR blijft staan voor postmortem: kubectl describe sparkapplication ${{NAME}} -n {NAMESPACE}"
      exit 1
      ;;
  esac
  sleep 10
done

echo "==> Timeout — SparkApplication ${{NAME}} draait nog na 25 min"
kubectl describe sparkapplication "${{NAME}}" -n {NAMESPACE} || true
exit 1
""".strip()
    ]


def _env_vars() -> list[V1EnvVar]:
    # Korte run-id: ds_nodash (YYYYMMDD) + try_number; past ruim binnen
    # Kubernetes' 63-char naam-limit voor "silver-wia-<RUN_ID>".
    return [
        V1EnvVar(
            name="AIRFLOW_RUN_ID",
            value="{{ ds_nodash }}-{{ ti.try_number }}",
        ),
    ]


def _jobs_volume() -> V1Volume:
    return V1Volume(
        name="airflow-jobs", config_map=V1ConfigMapVolumeSource(name=JOBS_CM)
    )


def _jobs_mount() -> V1VolumeMount:
    return V1VolumeMount(name="airflow-jobs", mount_path=JOBS_MOUNT, read_only=True)


with DAG(
    dag_id="transform_wia_spark",
    description=(
        "Spark-pad voor WIA bronze→silver→gold (parallel aan dbt). "
        "Tasks roepen SparkApplications aan in odap-platform namespace. "
        "Vereist seed-bronze-claims te zijn gedraaid (zie platform/08-spark/README.md)."
    ),
    default_args=DEFAULT_ARGS,
    schedule=None,
    start_date=datetime(2026, 5, 1),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["spark", "delta", "claims", "demo", "parallel-to-dbt"],
) as dag:
    silver = KubernetesPodOperator(
        task_id="silver_wia",
        name="silver-wia-launcher",
        namespace=NAMESPACE,
        image=KUBECTL_IMAGE,
        cmds=["bash", "-c"],
        arguments=_run_spark_app_cmd("spark-silver-wia.yaml", "silver-wia"),
        env_vars=_env_vars(),
        volumes=[_jobs_volume()],
        volume_mounts=[_jobs_mount()],
        container_resources=KUBECTL_POD_RESOURCES,
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        service_account_name="spark-launcher",
        outlets=[SILVER_DATASET],
    )

    gold = KubernetesPodOperator(
        task_id="gold_wia",
        name="gold-wia-launcher",
        namespace=NAMESPACE,
        image=KUBECTL_IMAGE,
        cmds=["bash", "-c"],
        arguments=_run_spark_app_cmd("spark-gold-wia.yaml", "gold-wia"),
        env_vars=_env_vars(),
        volumes=[_jobs_volume()],
        volume_mounts=[_jobs_mount()],
        container_resources=KUBECTL_POD_RESOURCES,
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
        service_account_name="spark-launcher",
        outlets=[GOLD_DATASET],
    )

    silver >> gold
