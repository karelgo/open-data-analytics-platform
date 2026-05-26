"""DAG-aanroeper — governance_om_ingest.

Vervangt eerdere om_ingest_trino.py + om_ingest_dbt.py: één DAG met twee
sequentiële taken. Trino-catalog eerst (anders heeft dbt-ingest geen tabel
om aan te koppelen), dan dbt-artifacts (lineage + meta).

Zie docs/adr/0007-airflow-pipeline-architecture.md.
SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from governance_factory import build_om_ingest_dag

dag = build_om_ingest_dag()
