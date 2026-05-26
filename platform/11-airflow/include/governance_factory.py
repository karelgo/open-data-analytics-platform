"""Governance-factory.

Bouwt twee soorten governance-DAGs:

  - om_ingest:    OpenMetadata-ingestion voor alle platform services
                  (Trino catalog + lineage + profiler, Superset, Airflow,
                  MinIO storage, dbt-artifacts + enricher).
                  Service-/workflow-YAMLs komen uit ConfigMap
                  `openmetadata-platform-config` (zie
                  platform/13-openmetadata-config/kustomization.yaml).
  - bewaartermijn: R-AVG-08 enforcement per tabel met meta.bewaartermijn_jaren.

Deze runnen op tijd-schema (geen Dataset-trigger) — ze leunen op rust-state.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client.models import V1EnvVar

from k8s_helpers import (
    SMALL_POD_RESOURCES,
    ca_mount,
    ca_volume,
    om_config_mount,
    om_config_volume,
    secret_env,
)

DEFAULT_ARGS = {
    "owner": "data-steward",
    "depends_on_past": False,
    "email_on_failure": False,
    # 2 retries om transient druk op de shared Postgres (Hive/OM/Airflow/
    # Superset delen één instance, max_connections=100) of korte OM-API
    # hapering te overleven. GEEN exponential backoff: de Airflow 3
    # KubernetesExecutor JWT-token heeft een TTL van 600s — als de
    # retry-wachttijd > 10min wordt, verloopt het token in de queued-fase
    # en faalt de retry met "Invalid auth token: Signature has expired".
    # 3min fixed retry-delay blijft ruim binnen het JWT-venster.
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    # Hard cap zodat een hangende OM-ingest niet uren in queued/running blijft
    # staan en de volgende scheduled-run blokkeert (max_active_runs=1).
    "execution_timeout": timedelta(minutes=20),
}

OM_INGESTION_IMAGE = "openmetadata/ingestion:1.12.8"


def _om_env_vars() -> list[V1EnvVar]:
    """Env-vars die de service-YAMLs envsubst'en (zie platform/13-openmetadata-config/services/).

    Alle Secrets moeten in de odap-platform namespace bestaan — de KPO draait
    daar. Bootstrap kopieert openmetadata-admin naar odap-platform zodat
    OM_JWT_TOKEN cross-namespace bereikbaar is.
    """
    return [
        # OM API sink — JWT van de ingestion-bot of een andere admin-bot.
        secret_env("OM_JWT_TOKEN", "openmetadata-admin", "jwtToken"),
        # Trino source — `smoketest` is de technische bot-user (zie OPA-rules).
        secret_env("TRINO_PASSWORD", "trino-static-users", "smoketest"),
        # MinIO source — voor dbt-manifest read.
        secret_env("MINIO_SECRET_KEY", "minio-s3-credentials", "secretKey"),
        # Airflow + Superset metadata-DBs.
        secret_env(
            "AIRFLOW_DB_PW",
            "airflow-postgres-credentials",
            "adminUser.password",
        ),
        secret_env(
            "SUPERSET_ADMIN_PW",
            "superset-postgres-credentials",
            "adminUser.password",
        ),
        # CA-bundle voor TLS-verify naar Trino + OM ingress.
        V1EnvVar(name="REQUESTS_CA_BUNDLE", value="/etc/platform-ca/ca.crt"),
        V1EnvVar(name="SSL_CERT_FILE", value="/etc/platform-ca/ca.crt"),
    ]


def _om_ingest_task(
    *, task_id: str, workflow_yaml: str, subcommand: str = "ingest"
) -> KubernetesPodOperator:
    """KPO die `metadata <subcommand> -c <workflow_yaml>` draait.

    workflow_yaml is het pad in de pod (gemount uit `openmetadata-platform-config`
    ConfigMap op /config). `subcommand` is "ingest" voor de meeste workflow-
    types (DatabaseMetadata/Lineage, Dashboard, Pipeline, Messaging, DBT) en
    "profile" voor type=Profiler.
    """
    return KubernetesPodOperator(
        task_id=task_id,
        namespace="odap-platform",
        image=OM_INGESTION_IMAGE,
        cmds=["bash", "-c"],
        # envsubst rendert ${VAR}-references uit de YAML op runtime.
        arguments=[
            f"envsubst < {workflow_yaml} > /tmp/run.yaml && "
            f"metadata {subcommand} -c /tmp/run.yaml"
        ],
        env_vars=_om_env_vars(),
        volumes=[ca_volume(), om_config_volume()],
        volume_mounts=[ca_mount(), om_config_mount()],
        container_resources=SMALL_POD_RESOURCES,
        is_delete_operator_pod=True,
        get_logs=True,
    )


def _om_enrich_task() -> KubernetesPodOperator:
    """KPO die `enrich_from_dbt_meta.py` draait — past dbt-meta toe als
    OM-tags / glossary-links / owner / tier / domain / dataProduct /
    custom-properties.

    Hergebruikt de OM-ingestion-image (heeft Python 3.10 + boto3 + requests +
    pyyaml standaard). Script + mapping zitten in dezelfde /config-mount."""
    return KubernetesPodOperator(
        task_id="enrich_om_from_dbt_meta",
        namespace="odap-platform",
        image=OM_INGESTION_IMAGE,
        cmds=["bash", "-c"],
        arguments=["python /config/enrich_from_dbt_meta.py"],
        env_vars=_om_env_vars(),
        volumes=[ca_volume(), om_config_volume()],
        volume_mounts=[ca_mount(), om_config_mount()],
        container_resources=SMALL_POD_RESOURCES,
        is_delete_operator_pod=True,
        get_logs=True,
    )


def build_om_ingest_dag() -> DAG:
    """Run de OM-ingests in een diamond-topologie rond Trino-catalog.

    Topologie:

                          ┌─ ingest_trino_lineage
                          ├─ ingest_trino_profiler
        ingest_trino_     ├─ ingest_superset
          catalog  ──────▶├─ ingest_airflow
        (must-succeed)    ├─ ingest_minio_storage
                          └─ ingest_dbt_artifacts ──▶ enrich_om_from_dbt_meta

    Workflow-YAMLs in `openmetadata-platform-config` ConfigMap (zie
    platform/13-openmetadata-config/services/).

    Catalog is de gedeelde voorwaarde: lineage/profiler hebben tabellen
    nodig om aan te koppelen; superset/airflow lineage refereren naar
    Trino-tables; dbt-models koppelen aan Trino-tabellen; enricher PATCH't
    /tables met dbt-meta-mapping. Catalog faalt → niets te ingesten →
    upstream_failed is correct.

    Side-services parallel ipv sequentieel: bij vorig ontwerp killde één
    profiler-failure de hele rest van de chain inclusief enricher (die juist
    de zichtbare governance-output produceert). Nu is iedere ingest een
    onafhankelijke tak; alleen enricher hangt op dbt-success.

    max_active_tasks=3 spreidt de fan-out zodat Trino/OM/Postgres niet
    tegelijk door 6 KPO-pods worden geraakt (shared Postgres heeft krappe
    max_connections=100).
    """
    with DAG(
        dag_id="governance_om_ingest",
        description=(
            "OpenMetadata-ingest van alle platform services: Trino (catalog + "
            "lineage + profiler), Superset, Airflow, MinIO en dbt-artifacts "
            "+ dbt-meta enricher."
        ),
        default_args=DEFAULT_ARGS,
        # 4-uurs schema ipv hourly: synthetic data verandert nauwelijks
        # tussen runs, en hourly ingest + profiler genereerde te veel druk
        # op de gedeelde Postgres (zie failure-log van 2026-05-19).
        schedule=timedelta(hours=4),
        start_date=datetime(2026, 5, 1),
        catchup=False,
        max_active_runs=1,
        # Cap de parallelle fan-out na catalog — voorkomt dat 6 KPO-pods
        # tegelijk de shared Postgres / OM API saturate.
        max_active_tasks=3,
        # uc11_full_setup triggert deze DAG op een verse cluster; zonder
        # is_paused_upon_creation=False blijft die call queued op een paused
        # DAG. catchup=False voorkomt backfill-explosie van het schema.
        is_paused_upon_creation=False,
        tags=["uwv", "governance", "openmetadata"],
    ) as dag:
        ingest_trino = _om_ingest_task(
            task_id="ingest_trino_catalog",
            workflow_yaml="/config/trino-service.yaml",
        )
        ingest_trino_lineage = _om_ingest_task(
            task_id="ingest_trino_lineage",
            workflow_yaml="/config/trino-lineage.yaml",
        )
        ingest_trino_profiler = _om_ingest_task(
            task_id="ingest_trino_profiler",
            workflow_yaml="/config/trino-profiler.yaml",
            # type=Profiler vereist `metadata profile` ipv `metadata ingest`
            # (anders: 'DatabaseServiceProfilerPipeline' has no attribute 'threads').
            subcommand="profile",
        )
        ingest_superset = _om_ingest_task(
            task_id="ingest_superset",
            workflow_yaml="/config/superset-service.yaml",
        )
        ingest_airflow = _om_ingest_task(
            task_id="ingest_airflow",
            workflow_yaml="/config/airflow-service.yaml",
        )
        ingest_minio = _om_ingest_task(
            task_id="ingest_minio_storage",
            workflow_yaml="/config/minio-storage.yaml",
        )
        ingest_dbt = _om_ingest_task(
            task_id="ingest_dbt_artifacts",
            workflow_yaml="/config/dbt-workflow.yaml",
        )
        enrich = _om_enrich_task()

        ingest_trino >> [
            ingest_trino_lineage,
            ingest_trino_profiler,
            ingest_superset,
            ingest_airflow,
            ingest_minio,
            ingest_dbt,
        ]
        ingest_dbt >> enrich
    return dag
