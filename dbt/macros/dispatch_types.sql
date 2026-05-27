{# Engine-agnostische SQL helpers via dbt's adapter.dispatch.

   Models die op zowel Trino als Databricks (Spark) moeten werken
   gebruiken deze macros i.p.v. engine-specifieke functies.

     {{ cast_string(field) }}        — Trino: varchar, Spark: string
     {{ cast_timestamp(field) }}     — Trino: timestamp(6), Spark: timestamp
     {{ date_diff_days(end, start) }} — Trino: date_diff('day',...), Spark: datediff(end,start)

   Voor een nieuwe target type (bv. snowflake) voeg je een
   <type>__<macro_name>.sql variant toe; default valt terug op Trino.
#}

{# ─── cast_string ─────────────────────────────────────────────────── #}
{% macro cast_string(field) %}
    {{ return(adapter.dispatch('cast_string')(field)) }}
{% endmacro %}

{% macro default__cast_string(field) -%}
    cast({{ field }} as varchar)
{%- endmacro %}

{% macro trino__cast_string(field) -%}
    cast({{ field }} as varchar)
{%- endmacro %}

{% macro databricks__cast_string(field) -%}
    cast({{ field }} as string)
{%- endmacro %}

{% macro spark__cast_string(field) -%}
    cast({{ field }} as string)
{%- endmacro %}


{# ─── cast_timestamp ──────────────────────────────────────────────── #}
{% macro cast_timestamp(field) %}
    {{ return(adapter.dispatch('cast_timestamp')(field)) }}
{% endmacro %}

{% macro default__cast_timestamp(field) -%}
    cast({{ field }} as timestamp(6))
{%- endmacro %}

{% macro trino__cast_timestamp(field) -%}
    cast({{ field }} as timestamp(6))
{%- endmacro %}

{% macro databricks__cast_timestamp(field) -%}
    cast({{ field }} as timestamp)
{%- endmacro %}

{% macro spark__cast_timestamp(field) -%}
    cast({{ field }} as timestamp)
{%- endmacro %}


{# ─── date_diff_days ──────────────────────────────────────────────── #}
{% macro date_diff_days(end_field, start_field) %}
    {{ return(adapter.dispatch('date_diff_days')(end_field, start_field)) }}
{% endmacro %}

{% macro default__date_diff_days(end_field, start_field) -%}
    date_diff('day', cast({{ start_field }} as date), cast({{ end_field }} as date))
{%- endmacro %}

{% macro trino__date_diff_days(end_field, start_field) -%}
    date_diff('day', cast({{ start_field }} as date), cast({{ end_field }} as date))
{%- endmacro %}

{% macro databricks__date_diff_days(end_field, start_field) -%}
    datediff(cast({{ end_field }} as date), cast({{ start_field }} as date))
{%- endmacro %}

{% macro spark__date_diff_days(end_field, start_field) -%}
    datediff(cast({{ end_field }} as date), cast({{ start_field }} as date))
{%- endmacro %}
