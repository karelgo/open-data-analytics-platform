"""DAG-aanroeper — gold_<uc>_<name> voor alle actieve use-cases.

Genereert 6 DAGs (één per UC met bestaande marts):
  gold_uc01_wia_funnel       (1 silver-trigger:  wia)
  gold_uc04_tw_eligibility   (3 triggers:        ww + polisadm + persoon)
  gold_uc05_client_360       (5 triggers:        persoon + polisadm + wia + crm + zw)
  gold_uc06_lastprognose     (1 trigger:         fez)
  gold_uc07_dq_polisadm      (1 trigger:         polisadm)
  gold_uc09_reint_effect     (2 triggers:        persoon + wia)

Elke DAG triggert pas wanneer ALLE benodigde silver-Datasets vers zijn.

Zie docs/adr/0007-airflow-pipeline-architecture.md.
SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from gold_factory import build_all_gold_dags

for dag_id, dag in build_all_gold_dags().items():
    globals()[dag_id] = dag
