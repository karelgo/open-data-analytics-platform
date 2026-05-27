{# Documentation-helper. Genereert geen SQL — bestaat zodat schema.yml in elke
   model een `meta.purpose-limitation`-array heeft die OpenMetadata's dbt-workflow
   oppikt en als classifications/tags propageert.

   Convention voor elk model in marts/* en bepaalde silver/* :
     meta:
       purpose-limitation: [claim payout, reintegration]
       legal_basis: WIA_art_64
       retention period_jaren: 7
       pii_kolommen: [bsn]
       risk_tier: laag

   Deze macro is een no-op; zie scripts/check-meta-completeness.py (TODO fase 9)
   voor CI-validatie dat elk model verplichte meta-velden heeft.
#}
{% macro apply_purpose-limitation_tag() %}
    -- no-op
{% endmacro %}
