"""convert_to_delta — generieke any-file → Delta conversie DAG.

Wordt getriggerd door de portal /csv-upload pagina via de airflow-bridge
sidecar (zie portal/scripts/airflow-bridge.py). Eén task: leest het
bestand uit `odap-staging/uploads/...`, parseert op basis van
`source_format` (csv/tsv/json/ndjson/parquet), schrijft Delta naar
`odap-{target_catalog}/{target_schema}/{target_table}/`, en registreert
de tabel in Hive Metastore via Trino.

Trigger-conf (verplicht):
  object_key      str   — s3-key binnen odap-staging (begint met "uploads/")
  source_format   str   — csv | tsv | json | ndjson | parquet
  target_schema   str   — snake_case (gevalideerd door bridge)
  target_table    str   — snake_case (gevalideerd door bridge)

Trigger-conf (optioneel):
  target_catalog  str   — bronze (default)
  partition_col   str   — bestaande kolom in input; default = event_date toegevoegd
  source_email    str   — ingelogde gebruiker (audit; alleen voor logging)

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client.models import (
    V1ConfigMapVolumeSource,
    V1EnvVar,
    V1Volume,
    V1VolumeMount,
)

from k8s_helpers import (
    SMALL_POD_RESOURCES,
    ca_mount,
    ca_volume,
    secret_env,
)

LOADER_IMAGE = "python:3.11-slim"

S3_ENDPOINT = "https://minio.odap-platform.svc.cluster.local:9000"
TRINO_HOST = "trino-coordinator.odap-platform.svc.cluster.local"
TRINO_PORT = "8443"
TRINO_USER = "smoketest"

JOBS_CM = "airflow-jobs"
JOBS_MOUNT = "/opt/odap/airflow/jobs"

DEFAULT_ARGS = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
}


def _pip_args() -> list[str]:
    """pip install loader-deps en run convert_to_delta.py."""
    return [
        "pip install --quiet --disable-pip-version-check "
        "--trusted-host pypi.org "
        "--trusted-host pypi.python.org "
        "--trusted-host files.pythonhosted.org "
        "'boto3>=1.34,<2' "
        "'pyarrow>=16,<18' "
        "'deltalake>=0.18,<0.20' "
        "'trino>=0.330,<0.340' && "
        f"python {JOBS_MOUNT}/convert_to_delta.py"
    ]


def _env_vars() -> list[V1EnvVar]:
    # Conf-velden worden via Jinja templating doorgegeven aan de pod.
    return [
        V1EnvVar(name="OBJECT_KEY", value="{{ dag_run.conf['object_key'] }}"),
        V1EnvVar(name="SOURCE_FORMAT", value="{{ dag_run.conf['source_format'] }}"),
        V1EnvVar(
            name="TARGET_CATALOG",
            value="{{ dag_run.conf.get('target_catalog', 'bronze') }}",
        ),
        V1EnvVar(name="TARGET_SCHEMA", value="{{ dag_run.conf['target_schema'] }}"),
        V1EnvVar(name="TARGET_TABLE", value="{{ dag_run.conf['target_table'] }}"),
        V1EnvVar(
            name="PARTITION_COL",
            value="{{ dag_run.conf.get('partition_col', '') }}",
        ),
        V1EnvVar(
            name="SOURCE_EMAIL", value="{{ dag_run.conf.get('source_email', '') }}"
        ),
        V1EnvVar(name="STAGING_BUCKET", value="odap-staging"),
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
        # CA-bundle
        V1EnvVar(name="REQUESTS_CA_BUNDLE", value="/etc/platform-ca/ca.crt"),
        V1EnvVar(name="SSL_CERT_FILE", value="/etc/platform-ca/ca.crt"),
    ]


with DAG(
    dag_id="convert_to_delta",
    description=(
        "Generieke any-file → Delta-conversie. Wordt getriggerd vanuit de portal "
        "/csv-upload pagina via de airflow-bridge sidecar; leest het bestand uit "
        "odap-staging/uploads/, schrijft Delta naar odap-<catalog>/<schema>/<table>/, "
        "en registreert in Hive Metastore via Trino."
    ),
    default_args=DEFAULT_ARGS,
    schedule=None,  # alleen via REST trigger
    start_date=datetime(2026, 5, 1),
    catchup=False,
    max_active_runs=4,  # meerdere parallelle uploads OK
    is_paused_upon_creation=False,
    params={
        "object_key": "uploads/<email>/<ts>/<file>",
        "source_format": "csv",
        "target_catalog": "bronze",
        "target_schema": "sandbox",
        "target_table": "my_table",
        "partition_col": "",
    },
    tags=["convert", "delta", "any-file", "portal-trigger"],
) as dag:
    KubernetesPodOperator(
        task_id="convert",
        name="convert-to-delta",
        namespace="odap-platform",
        image=LOADER_IMAGE,
        cmds=["bash", "-euo", "pipefail", "-c"],
        arguments=_pip_args(),
        env_vars=_env_vars(),
        volumes=[
            ca_volume(),
            V1Volume(
                name="airflow-jobs", config_map=V1ConfigMapVolumeSource(name=JOBS_CM)
            ),
        ],
        volume_mounts=[
            ca_mount(),
            V1VolumeMount(name="airflow-jobs", mount_path=JOBS_MOUNT, read_only=True),
        ],
        container_resources=SMALL_POD_RESOURCES,
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )
