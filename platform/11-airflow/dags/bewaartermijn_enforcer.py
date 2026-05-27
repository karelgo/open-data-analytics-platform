"""DAG: retention period-enforcer (R-AVG-08, improvements #9).

Loopt dagelijks. Per tabel: DELETE waar `event_date < current_date - interval
<retention period_jaren>`. Retention perioden zijn afgeleid uit dbt-meta in elke
mart's `_*.yml` (zie compliance-mapping).

Production-overweging: voor immutable Delta-tabellen is `DELETE FROM` mogelijk
maar zwaarder dan een PARTITION DROP. Voor dagelijks-gepartitioneerde tabellen
zou een aparte DROP PARTITION-pad efficiënter zijn.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.providers.trino.operators.trino import TrinoOperator

DEFAULT_ARGS = {
    "owner": "data-steward",
    "depends_on_past": False,
    "email_on_failure": True,
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
}

# Retention period per tabel (jaren). Bron: dbt schema.yml `meta.retention period_jaren`.
# In production zou dit dynamisch via OpenMetadata custom-properties komen.
RETENTION_RULES = [
    # (catalog, schema, table, year_column, retention_years, dry_run_only)
    ("silver", "customers", "stg_customer_interaction", "event_date", 2, False),
    ("bronze", "demo", "customer_interaction", "event_date", 2, False),
    (
        "silver",
        "finance",
        "stg_finance_expense",
        "event_date",
        10,
        True,
    ),  # publiek-publiceerbaar; bewust dry-run
    (
        "gold",
        "uc01_claims_funnel",
        "mart_uc01_claims_funnel_daily",
        "aanvraag_datum",
        7,
        False,
    ),
    (
        "gold",
        "uc05_customer_360",
        "mart_uc05_customer_360",
        None,
        7,
        True,
    ),  # geen tijdsdimensie; alleen flag
    ("silver", "audit", "client_360_reads", "event_date", 7, False),
]


def _delete_sql(
    catalog: str,
    schema: str,
    table: str,
    year_col: str | None,
    years: int,
    dry_run: bool,
) -> str:
    fq = f'"{catalog}"."{schema}"."{table}"'
    if year_col is None:
        # Geen tijdsdimensie — geen automatische cleanup mogelijk.
        return f"-- {fq}: geen year_column; manuele cleanup vereist."
    threshold = f"current_date - interval '{years}' year"
    if dry_run:
        return (
            f"SELECT count(*) AS would_delete FROM {fq} "
            f"WHERE {year_col} < {threshold};"
        )
    return f"DELETE FROM {fq} WHERE {year_col} < {threshold};"


with DAG(
    dag_id="retention period_enforcer",
    description="Dagelijkse retention period-enforcement (R-AVG-08).",
    default_args=DEFAULT_ARGS,
    schedule="0 4 * * *",  # 04:00 UTC daily, low-traffic window
    start_date=datetime(2026, 5, 1),
    catchup=False,
    max_active_runs=1,
    tags=["compliance", "avg", "demo", "improvements-9"],
) as dag:
    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    for catalog, schema, table, year_col, years, dry_run in RETENTION_RULES:
        sql = _delete_sql(catalog, schema, table, year_col, years, dry_run)
        task_id = f"retention_{catalog}_{schema}_{table}"
        if dry_run:
            task_id += "__dry_run"
        op = TrinoOperator(
            task_id=task_id,
            trino_conn_id="trino_default",
            sql=sql,
            handler=lambda result: None,  # we hoeven geen XCom-resultaat
        )
        start >> op >> end
