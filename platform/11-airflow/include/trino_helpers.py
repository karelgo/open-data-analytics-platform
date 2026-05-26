"""Trino-connectiehelpers — gedeeld door Cosmos en KubernetesPodOperator-DAGs.

Twee paden:
  - Cosmos: ProfileMapping leest uit een Airflow Connection (default `trino_default`).
  - KubernetesPodOperator: env-vars voor dbt-image (legacy compat).
"""
from __future__ import annotations

from kubernetes.client.models import (
    V1EnvVar,
    V1EnvVarSource,
    V1SecretKeySelector,
)

# Defaults — overrideable via Airflow Variables.
TRINO_HOST = "trino-coordinator.odap-platform.svc.cluster.local"
TRINO_PORT = "8443"
TRINO_USER = "smoketest"
TRINO_USER_SECRET = "trino-static-users"     # Stackable secret
TRINO_USER_SECRET_KEY = "smoketest"
TRINO_CONN_ID = "trino_default"                  # Airflow Connection-id voor Cosmos


def trino_pod_env() -> list[V1EnvVar]:
    """Env-vars voor dbt-trino dbt-runs in een KubernetesPodOperator."""
    return [
        V1EnvVar(name="TRINO_HOST", value=TRINO_HOST),
        V1EnvVar(name="TRINO_PORT", value=TRINO_PORT),
        V1EnvVar(name="TRINO_USER", value=TRINO_USER),
        V1EnvVar(
            name="TRINO_PASSWORD",
            value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(
                    name=TRINO_USER_SECRET,
                    key=TRINO_USER_SECRET_KEY,
                )
            ),
        ),
        V1EnvVar(name="TABLE_FORMAT", value="delta"),
        V1EnvVar(name="DBT_PROFILES_DIR", value="/workspace/repo/dbt"),
    ]
