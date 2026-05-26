"""DAG-aanroeper — manuele CSV-ingest per csv_batch-bron.

Eén DAG per bron met `mode: csv_batch` in de source-YAML. Trigger handmatig
via de Airflow UI ("Trigger DAG w/ config") met:

    {"object_key": "incoming/<bron>/<bestand>.csv"}

Zie docs/handbooks/csv-upload.md voor de end-to-end runbook.
SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from csv_ingest_factory import build_all_csv_ingest_dags

# Eén DAG per csv_batch-bron — Airflow pakt deze module-globals automatisch op.
for dag_id, dag in build_all_csv_ingest_dags().items():
    globals()[dag_id] = dag
