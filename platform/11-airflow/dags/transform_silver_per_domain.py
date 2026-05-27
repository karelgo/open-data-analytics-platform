"""DAG-aanroeper — silver_<domain> voor alle 8 domeinen.

Genereert 8 DAGs (één per bron from the YAML-registry):
  silver_persoon, silver_polisadm, silver_ww, silver_wia,
  silver_wajong, silver_zw, silver_crm, silver_fez

Elke DAG:
  - Schedule: bronze-Dataset van die bron
  - Body: Cosmos genereert taak per dbt-staging-model met dat tag
  - Output: silver-Dataset (triggert gold-DAGs)

Zie docs/adr/0007-airflow-pipeline-architecture.md.
SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from silver_factory import build_all_silver_dags

# Cosmos vereist dat DAG-objecten op module-niveau bestaan.
# globals().update() registreert ze bij Airflow's DagBag.
for dag_id, dag in build_all_silver_dags().items():
    globals()[dag_id] = dag
