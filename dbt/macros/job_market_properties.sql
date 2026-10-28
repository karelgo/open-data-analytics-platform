{% macro job_market_properties(name) %}
  {{ return(table_format_properties(extra_props={'location': "'s3a://odap-gold/job-market/" ~ name ~ "/'"})) }}
{% endmacro %}
