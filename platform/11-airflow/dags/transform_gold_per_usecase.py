"""DAG-aanroeper — gold_<uc>_<name> voor alle actieve use-cases.

Genereert 6 DAGs (één per UC met bestaande marts):
  gold_uc01_claims_funnel       (1 silver-trigger:  wia)
  gold_uc04_eligibility_outreach   (3 triggers:        ww + polisadm + persoon)
  gold_uc05_customer_360       (5 triggers:        persoon + polisadm + wia + crm + zw)
  gold_uc06_cost_forecast     (1 trigger:         fez)
  gold_uc07_dq_policies      (1 trigger:         polisadm)
  gold_uc09_reintegration_effect     (2 triggers:        persoon + wia)

Elke DAG triggert pas wanneer ALLE benodigde silver-Datasets vers zijn.

Zie docs/adr/0007-airflow-pipeline-architecture.md.
SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""

from __future__ import annotations

from gold_factory import build_all_gold_dags

for dag_id, dag in build_all_gold_dags().items():
    globals()[dag_id] = dag
