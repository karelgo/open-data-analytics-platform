{# Target-aware schema-bootstrap voor het ODAP platform.

   Gebruik (in dbt_project.yml):
     on-run-start: "{{ ensure_schemas() }}"

   Per target:
   - trino    → CREATE SCHEMA ... WITH (location = 's3a://odap-<layer>/<name>/')
                voor elke silver/gold-schema (huidige Stackable-gedrag).
                Stackable's Hive-Metastore heeft geen globale warehouse.dir,
                dus elke schema MOET een expliciete S3-locatie hebben.
   - databricks → no-op. Unity Catalog catalog/schemas worden out-of-band
                  aangemaakt (eenmalig, via Databricks SQL of Terraform).
                  Tabellen zijn UC-managed; geen schema-locaties nodig.
   - fabric / fabricspark → no-op. Lakehouse + schemas worden via Fabric REST
                  voorgekookt door de uc11_fabric Airflow-DAG (eerste task).
   - default → no-op + waarschuwing, zodat onbekende targets niet stilletjes
               schema-creatie missen.
#}
{% macro ensure_schemas() %}
    {%- set silver_schemas = [
        'persons', 'policies', 'service_requests', 'claims', 'eligibility_cases', 'incidents', 'customers',
        'finance', 'klantcontact', 'finops', 'intermediate', 'sandbox_uc09', 'seed'
    ] -%}
    {%- set gold_schemas = [
        'uc01_claims_funnel', 'uc04_eligibility_outreach', 'uc05_customer_360',
        'uc06_cost_forecast', 'uc07_dq_policies', 'uc09_reintegration_effect',
        'uc11_customer_journey', 'uc12_focus_finops', 'uc_customer_satisfaction',
        'dq_overview', 'seed'
    ] -%}

    {%- if target.type == 'trino' -%}
        {%- if execute -%}
            {%- for s in silver_schemas -%}
                {%- do run_query(
                    "CREATE SCHEMA IF NOT EXISTS silver." ~ s ~
                    " WITH (location = 's3a://odap-silver/" ~ s ~ "/')"
                ) -%}
            {%- endfor -%}
            {%- for g in gold_schemas -%}
                {%- do run_query(
                    "CREATE SCHEMA IF NOT EXISTS gold." ~ g ~
                    " WITH (location = 's3a://odap-gold/" ~ g ~ "/')"
                ) -%}
            {%- endfor -%}
        {%- endif -%}
        SELECT 1 AS schemas_ensured_trino
    {%- elif target.type == 'databricks' -%}
        SELECT 1 AS schemas_skipped_databricks_managed_by_uc
    {%- elif target.type in ('fabric', 'fabricspark') -%}
        SELECT 1 AS schemas_skipped_fabric_managed_by_airflow
    {%- else -%}
        {{ log("WARN: ensure_schemas() — onbekende target.type='" ~ target.type ~ "'; schema-creatie overgeslagen", info=true) }}
        SELECT 1 AS schemas_skipped_unknown_target
    {%- endif -%}
{% endmacro %}
