"""One daily Dutch IT jobs example: extract -> Delta -> dbt tests -> catalog -> BI."""

import os
from datetime import timedelta

import pendulum
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.sdk import DAG
from governance_factory import _om_enrich_task, _om_ingest_task
from k8s_helpers import ca_mount, ca_volume, secret_env
from kubernetes.client import models as k8s

IMAGE = os.getenv("JOB_MARKET_IMAGE", "odap/job-market:dev")
DATE = "{{ data_interval_end.in_timezone('Europe/Amsterdam').strftime('%Y-%m-%d') }}"


def stage(task_id):
    return KubernetesPodOperator(
        task_id=task_id,
        name=f"jobs-{task_id}",
        namespace="odap-platform",
        image=IMAGE,
        cmds=["python", "/opt/job-market/runtime.py"],
        arguments=[task_id, "--date", DATE],
        env_vars=[
            secret_env("S3_ACCESS_KEY", "minio-s3-credentials", "accessKey"),
            secret_env("S3_SECRET_KEY", "minio-s3-credentials", "secretKey"),
            k8s.V1EnvVar(name="REQUESTS_CA_BUNDLE", value="/etc/platform-ca/ca.crt"),
        ],
        env_from=[
            k8s.V1EnvFromSource(
                config_map_ref=k8s.V1ConfigMapEnvSource(name="job-market-settings")
            ),
            k8s.V1EnvFromSource(
                secret_ref=k8s.V1SecretEnvSource(
                    name="job-market-api-credentials", optional=True
                )
            ),
        ],
        service_account_name="spark-launcher",
        volumes=[ca_volume()],
        volume_mounts=[ca_mount()],
        container_resources=k8s.V1ResourceRequirements(
            requests={"cpu": "100m", "memory": "256Mi"},
            limits={"cpu": "1000m", "memory": "1Gi"},
        ),
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )


def dashboard_task(task_id, config_map, filename):
    return KubernetesPodOperator(
        task_id=task_id,
        name=task_id,
        namespace="odap-platform",
        image=IMAGE,
        cmds=["python", f"/scripts/{filename}"],
        env_vars=[
            secret_env(
                "ADMIN_USER", "superset-postgres-credentials", "adminUser.username"
            ),
            secret_env(
                "ADMIN_PASSWORD", "superset-postgres-credentials", "adminUser.password"
            ),
            secret_env("TRINO_PASSWORD", "trino-static-users", "smoketest"),
            k8s.V1EnvVar(name="REQUESTS_CA_BUNDLE", value="/etc/platform-ca/ca.crt"),
        ],
        volumes=[
            ca_volume(),
            k8s.V1Volume(
                name="scripts", config_map=k8s.V1ConfigMapVolumeSource(name=config_map)
            ),
        ],
        volume_mounts=[
            ca_mount(),
            k8s.V1VolumeMount(name="scripts", mount_path="/scripts", read_only=True),
        ],
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )


with DAG(
    dag_id="dutch_it_jobs_daily",
    description="Dutch IT jobs: one daily platform-wide example",
    schedule="0 5 * * *",
    start_date=pendulum.datetime(2026, 10, 1, tz="Europe/Amsterdam"),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    default_args={
        "owner": "labour-market-data-team",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(minutes=40),
    },
    tags=["job-market", "daily", "data", "cloud", "sap", "ai", "software", "security"],
) as dag:
    extract = stage("extract")
    bronze = stage("bronze")
    transform = stage("transform")
    catalog = _om_ingest_task(
        task_id="catalog_jobs", workflow_yaml="/config/trino-service.yaml"
    )
    lineage = _om_ingest_task(
        task_id="dbt_lineage_and_tests", workflow_yaml="/config/dbt-workflow.yaml"
    )
    enrich = _om_enrich_task()
    datasets = dashboard_task(
        "register_job_datasets", "superset-init-script", "init_superset.py"
    )
    dashboard = dashboard_task(
        "publish_job_dashboard",
        "superset-dashboards-init-script",
        "build_dashboards.py",
    )
    (
        extract
        >> bronze
        >> transform
        >> catalog
        >> lineage
        >> enrich
        >> datasets
        >> dashboard
    )
