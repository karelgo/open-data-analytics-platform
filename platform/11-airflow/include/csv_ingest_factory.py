"""CSV-ingest-factory.

Bouwt één DAG per `csv_batch`-bron. Elke DAG heeft één KubernetesPodOperator-
task die `csv_to_bronze.py` runt — leest CSV uit s3://odap-staging/<prefix>/...,
valideert tegen het schema in de source-YAML, schrijft Delta naar bronze, en
publiceert de bronze-Dataset zodat silver-DAGs auto-getriggerd worden.

Trigger: handmatig via Airflow UI met `dag_run.conf = {"object_key": "..."}`.
Optioneel kan later een sensor toegevoegd worden die `incoming/<bron>/` polt.

Pattern volgt governance_factory._om_ingest_task — pip install at runtime
i.p.v. een dedicated image, om bouw-overhead te besparen for the referentie.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client.models import V1ConfigMapVolumeSource, V1EnvVar, V1Volume, V1VolumeMount

from datasets import bronze_dataset
from k8s_helpers import (
    SMALL_POD_RESOURCES,
    ca_mount,
    ca_volume,
    secret_env,
)
from sources_loader import SourceSpec, csv_batch_sources

DEFAULT_ARGS = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 0,                          # Idempotent: re-trigger met zelfde key faalt op move-to-processed.
    "retry_delay": timedelta(minutes=2),
}

# Image — slank Python-base. pip install van loader-deps gebeurt in args.
LOADER_IMAGE = "python:3.11-slim"

# Endpoints in-cluster. CA voor TLS-verify komt uit platform-ca-bundle ConfigMap.
S3_ENDPOINT = "https://minio.odap-platform.svc.cluster.local:9000"
TRINO_HOST = "trino-coordinator.odap-platform.svc.cluster.local"
TRINO_PORT = "8443"
TRINO_USER = "smoketest"                   # static-user voor automation; OPA staat HMS-DDL toe.

# ConfigMap-namen — gegenereerd door platform/11-airflow/kustomization.yaml.
SOURCES_CM = "airflow-sources"
JOBS_CM = "airflow-jobs"

JOBS_VOLUME = "airflow-jobs"
JOBS_MOUNT = "/opt/odap/airflow/jobs"
SOURCES_VOLUME = "airflow-sources"
SOURCES_MOUNT = "/opt/odap/airflow/sources"


def _jobs_volume() -> V1Volume:
    return V1Volume(name=JOBS_VOLUME, config_map=V1ConfigMapVolumeSource(name=JOBS_CM))


def _jobs_mount() -> V1VolumeMount:
    return V1VolumeMount(name=JOBS_VOLUME, mount_path=JOBS_MOUNT, read_only=True)


def _sources_volume() -> V1Volume:
    return V1Volume(name=SOURCES_VOLUME, config_map=V1ConfigMapVolumeSource(name=SOURCES_CM))


def _sources_mount() -> V1VolumeMount:
    return V1VolumeMount(name=SOURCES_VOLUME, mount_path=SOURCES_MOUNT, read_only=True)


def _env_vars(source: SourceSpec) -> list[V1EnvVar]:
    return [
        V1EnvVar(name="SOURCE_NAME", value=source.name),
        # object_key komt uit dag_run.conf — Jinja-rendered op task-level.
        V1EnvVar(name="OBJECT_KEY", value="{{ dag_run.conf['object_key'] }}"),
        V1EnvVar(name="SOURCES_DIR", value=SOURCES_MOUNT),
        V1EnvVar(name="BRONZE_BUCKET", value="odap-bronze"),
        # MinIO
        V1EnvVar(name="S3_ENDPOINT", value=S3_ENDPOINT),
        V1EnvVar(name="S3_REGION", value="eu-nl-1"),
        secret_env("S3_ACCESS_KEY", "minio-s3-credentials", "accessKey"),
        secret_env("S3_SECRET_KEY", "minio-s3-credentials", "secretKey"),
        # Trino
        V1EnvVar(name="TRINO_HOST", value=TRINO_HOST),
        V1EnvVar(name="TRINO_PORT", value=TRINO_PORT),
        V1EnvVar(name="TRINO_USER", value=TRINO_USER),
        V1EnvVar(name="TRINO_HTTP_SCHEME", value="https"),
        V1EnvVar(name="TRINO_VERIFY", value="/etc/platform-ca/ca.crt"),
        secret_env("TRINO_PASSWORD", "trino-static-users", TRINO_USER),
        # CA-bundle voor TLS-verify (MinIO + Trino zijn beide cert-manager).
        V1EnvVar(name="REQUESTS_CA_BUNDLE", value="/etc/platform-ca/ca.crt"),
        V1EnvVar(name="SSL_CERT_FILE", value="/etc/platform-ca/ca.crt"),
    ]


def _pip_args() -> list[str]:
    """Eén command-string voor `bash -c`. pip install + run script.

    Versies gepind om reproduceerbare runs te krijgen — bij upgrade pas hier
    bumpen, niet in losse YAML-files.

    `--trusted-host` is nodig omdat we SSL_CERT_FILE/REQUESTS_CA_BUNDLE op de
    Platform CA hebben staan (voor MinIO + Trino TLS-verify in de runtime). Pip's
    TLS-stack zou dan PyPI's publieke CA niet vertrouwen — daarom expliciet
    de PyPI-hosts whitelisten i.p.v. de CA-vars te unsetten.
    """
    return [
        "pip install --quiet --disable-pip-version-check "
        "--trusted-host pypi.org "
        "--trusted-host pypi.python.org "
        "--trusted-host files.pythonhosted.org "
        "'boto3>=1.34,<2' "
        "'pyarrow>=16,<18' "
        "'deltalake>=0.18,<0.20' "
        "'trino>=0.330,<0.340' "
        "'PyYAML>=6,<7' && "
        f"python {JOBS_MOUNT}/csv_to_bronze.py"
    ]


def build_csv_ingest_dag(source: SourceSpec) -> DAG:
    """DAG voor één csv_batch-bron — handmatig getriggerd via dag_run.conf."""
    if source.csv_ingest is None:
        raise ValueError(f"{source.name}: csv_ingest spec ontbreekt (mode != csv_batch?)")

    dag_id = f"ingest_csv_{source.name}"
    description = (
        f"Manuele CSV-ingest voor bron {source.name!r} → "
        f"{source.bronze.fqn}. Trigger via Airflow UI met "
        f"conf={{\"object_key\": \"{source.csv_ingest.staging_prefix}/<bestand>.csv\"}}."
    )

    with DAG(
        dag_id=dag_id,
        description=description,
        default_args=DEFAULT_ARGS,
        schedule=None,                     # Alleen handmatig.
        start_date=datetime(2026, 5, 1),
        catchup=False,
        max_active_runs=1,
        params={
            # Render in UI als verplicht text-veld bij "Trigger DAG w/ config".
            "object_key": f"{source.csv_ingest.staging_prefix}/<bestand>.csv",
        },
        tags=source.airflow_tags + ["ingest", "csv"],
        render_template_as_native_obj=False,
    ) as dag:
        KubernetesPodOperator(
            task_id="csv_to_bronze",
            namespace="odap-platform",
            image=LOADER_IMAGE,
            cmds=["bash", "-euo", "pipefail", "-c"],
            arguments=_pip_args(),
            env_vars=_env_vars(source),
            volumes=[ca_volume(), _jobs_volume(), _sources_volume()],
            volume_mounts=[ca_mount(), _jobs_mount(), _sources_mount()],
            container_resources=SMALL_POD_RESOURCES,
            is_delete_operator_pod=True,
            get_logs=True,
            outlets=[bronze_dataset(source)],
        )

    return dag


def build_all_csv_ingest_dags() -> dict[str, DAG]:
    return {
        f"ingest_csv_{s.name}": build_csv_ingest_dag(s)
        for s in csv_batch_sources()
    }
