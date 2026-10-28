"""Catalog, dbt lineage and metadata enrichment for the daily job-market DAG."""

from __future__ import annotations

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from k8s_helpers import (
    SMALL_POD_RESOURCES,
    ca_mount,
    ca_volume,
    om_config_mount,
    om_config_volume,
    secret_env,
)
from kubernetes.client.models import V1EnvVar

OM_INGESTION_IMAGE = "openmetadata/ingestion:1.12.8"


def _om_env_vars():
    return [
        secret_env("OM_JWT_TOKEN", "openmetadata-admin", "jwtToken"),
        secret_env("TRINO_PASSWORD", "trino-static-users", "smoketest"),
        secret_env("MINIO_SECRET_KEY", "minio-s3-credentials", "secretKey"),
        secret_env("MINIO_ACCESS_KEY", "minio-s3-credentials", "accessKey"),
        V1EnvVar(
            name="MINIO_ENDPOINT",
            value="https://minio.odap-platform.svc.cluster.local:9000",
        ),
        V1EnvVar(name="REQUESTS_CA_BUNDLE", value="/etc/platform-ca/ca.crt"),
        V1EnvVar(name="SSL_CERT_FILE", value="/etc/platform-ca/ca.crt"),
        V1EnvVar(name="AWS_CA_BUNDLE", value="/etc/platform-ca/ca.crt"),
    ]


def _task(task_id, command):
    return KubernetesPodOperator(
        task_id=task_id,
        namespace="odap-platform",
        image=OM_INGESTION_IMAGE,
        cmds=["bash", "-ec"],
        arguments=[command],
        env_vars=_om_env_vars(),
        volumes=[ca_volume(), om_config_volume()],
        volume_mounts=[ca_mount(), om_config_mount()],
        container_resources=SMALL_POD_RESOURCES,
        is_delete_operator_pod=True,
        get_logs=True,
        in_cluster=True,
    )


def _om_ingest_task(*, task_id, workflow_yaml, subcommand="ingest"):
    return _task(
        task_id,
        f"envsubst < {workflow_yaml} > /tmp/run.yaml && metadata {subcommand} -c /tmp/run.yaml",
    )


def _om_enrich_task():
    return _task("enrich_job_market_metadata", "python /config/enrich_from_dbt_meta.py")
