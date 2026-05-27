"""DAG: lakehouse maintenance — format-aware OPTIMIZE/VACUUM.

- Delta: `OPTIMIZE table` (z-order optioneel) + `VACUUM table RETAIN 168 HOURS`
- Iceberg: native procedures `expire_snapshots` + `rewrite_data_files`
  + `remove_orphan_files`

Selecteert format vanuit Airflow Variable `table_format` (default 'delta').
Per bronze/silver/gold-tabel één task; faalt graceful als tabel niet bestaat.

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.empty import EmptyOperator
from airflow.providers.trino.operators.trino import TrinoOperator

# Welke tabellen onderhouden? Voor de smoke houden we het bij de bronze-laag.
# Production: dynamisch via SHOW TABLES of een meta-tabel die OM voorziet.
MAINTAIN_TABLES = [
    ("bronze", "demo", "person_created"),
    ("bronze", "demo", "policy_holders"),
    ("bronze", "demo", "service_request_application"),
    ("bronze", "demo", "claim_application"),
    ("bronze", "demo", "eligibility_case"),
    ("bronze", "demo", "incident_report"),
    ("bronze", "demo", "customer_interaction"),
    ("bronze", "demo", "finance_expense"),
]

DEFAULT_ARGS = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}


def _maintenance_sql(catalog: str, schema: str, table: str, fmt: str) -> str:
    """SQL-payload per tabel + format."""
    fq = f'"{catalog}"."{schema}"."{table}"'
    if fmt == "delta":
        # Delta-Lake connector procedures in Trino:
        return (
            f"ALTER TABLE {fq} EXECUTE OPTIMIZE; "
            f"ALTER TABLE {fq} EXECUTE VACUUM (retention => '7d');"
        )
    if fmt == "iceberg":
        return (
            f"ALTER TABLE {fq} EXECUTE expire_snapshots(retention_threshold => '7d'); "
            f"ALTER TABLE {fq} EXECUTE remove_orphan_files(retention_threshold => '7d'); "
            f"ALTER TABLE {fq} EXECUTE optimize;"
        )
    raise ValueError(f"Onbekend table_format: {fmt!r}")


with DAG(
    dag_id="lakehouse_maintenance",
    description="Per-tabel OPTIMIZE/VACUUM (Delta) of expire_snapshots (Iceberg).",
    default_args=DEFAULT_ARGS,
    schedule="@daily",
    start_date=datetime(2026, 5, 1),
    catchup=False,
    max_active_runs=1,
    tags=["maintenance", "demo", "fase-6"],
) as dag:
    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    fmt = Variable.get("table_format", default_var="delta")

    for catalog, schema, table in MAINTAIN_TABLES:
        op = TrinoOperator(
            task_id=f"maintain_{catalog}_{schema}_{table}",
            trino_conn_id="trino_default",  # opgezet via Airflow Connection
            sql=_maintenance_sql(catalog, schema, table, fmt),
        )
        start >> op >> end
