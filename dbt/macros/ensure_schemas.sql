{% macro ensure_schemas() %}
  {% if target.type != 'trino' %}
    {{ exceptions.raise_compiler_error('The Dutch IT jobs reference pipeline currently supports dbt-trino.') }}
  {% endif %}
  {% if execute %}
    {# The three Trino catalogs share HMS. Names are unique across layers;
       each persisted mart supplies its own layer-specific table location. #}
    {% do run_query("CREATE SCHEMA IF NOT EXISTS bronze.job_market WITH (location = 's3a://odap-bronze/job-market/')") %}
  {% endif %}
  SELECT 1 AS job_market_schema_ready
{% endmacro %}
