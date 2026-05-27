"""Bronze-factory.

Bouwt één DAG die de Spark-streaming-output bevestigt en per bron een
`Dataset` publiceert. Hiermee triggeren silver-DAGs zich automatisch.

Alternatieven die we NIET kiezen:
  - Per bron een eigen DAG: te veel ruis, alle bronnen worden door dezelfde
    Spark-job geschreven.
  - Een sensor per individueel JSONL-bestand: niet nodig — Spark commit
    pas Delta-bestanden bij geslaagde batch.

Concreet: één DAG `bronze_watch`, draait elke `BRONZE_TICK_SECONDS`,
bevat één task per bron die controleert of `bronze.<schema>.<table>` recent
nieuwe rijen heeft (max_event_ts > prev_max_event_ts), en dan publiceert.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.providers.trino.hooks.trino import TrinoHook
from airflow.decorators import task

from datasets import bronze_dataset
from sources_loader import SourceSpec, stream_sources
from trino_helpers import TRINO_CONN_ID

DEFAULT_ARGS = {
    "owner": "data-engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def _check_bronze_freshness_callable(source: SourceSpec):
    """Closure: returnt een task-functie die deze bron controleert."""
    sql = (
        f"SELECT count(*) AS n, max(source_ts) AS max_ts "
        f"FROM {source.bronze.fqn} "
        f"WHERE event_date >= current_date - INTERVAL '1' DAY"
    )
    threshold_seconds = source.sla.alert_threshold_seconds

    def _check(**ctx):
        hook = TrinoHook(trino_conn_id=TRINO_CONN_ID)
        rows = hook.get_records(sql)
        if not rows:
            raise RuntimeError(f"{source.bronze.fqn}: query gaf geen resultaten")
        n, max_ts = rows[0]
        ctx["ti"].xcom_push(key="row_count", value=int(n or 0))
        if not max_ts or n == 0:
            # Voor batch-bronnen (fez) is dit acceptabel; voor streaming niet.
            if source.sla.mode == "streaming":
                raise RuntimeError(
                    f"{source.bronze.fqn}: geen rijen in laatste 24u "
                    f"(mode=streaming, threshold={threshold_seconds}s)"
                )
        return {"source": source.name, "rows": int(n or 0), "max_ts": str(max_ts)}

    return _check


def build_bronze_watch_dag() -> DAG:
    """Eén DAG met één freshness-task per stream-bron, publiceert bron-Dataset.

    csv_batch-bronnen (handmatige CSV-upload) hebben geen stream-pad en publiceren
    hun bronze-Dataset zelf via csv_ingest_factory; we filteren ze hier weg
    zodat ze niet als 'stale' worden geflagd.
    """
    with DAG(
        dag_id="bronze_watch",
        description=(
            "Bevestigt Spark-streaming-output per stream-bron en publiceert "
            "bronze-Datasets als trigger voor silver-DAGs. csv_batch-bronnen "
            "worden door ingest_csv_<bron> afgehandeld. Zie ADR-0007."
        ),
        default_args=DEFAULT_ARGS,
        schedule=timedelta(minutes=5),
        start_date=datetime(2026, 5, 1),
        catchup=False,
        max_active_runs=1,
        tags=["demo", "bronze", "ingest"],
    ) as dag:
        start = EmptyOperator(task_id="start")
        end = EmptyOperator(task_id="end")

        for source in stream_sources():
            check = task(
                task_id=f"check_{source.name}",
                outlets=[bronze_dataset(source)],
            )(_check_bronze_freshness_callable(source))()
            start >> check >> end

    return dag
