{# Schema resolutie per target:

   - trino: gebruik letterlijk de custom schema-naam (bv. `silver.ww`,
     `gold.uc01_*`). dbt zou anders prefixen met `target.schema_<custom>`.
   - databricks: UC heeft één catalog (databricks). Staging + intermediate
     gaan naar `silver`-schema; marts naar `gold`-schema. Mapping op basis
     van `node.config.database` (de `+database:` waarde uit dbt_project.yml,
     die in Trino-context de catalog-naam is).
   - fabricspark: non-schema Lakehouse heeft één namespace per Lakehouse;
     custom schemas zoals `intermediate` of `uc11_customer_journey` bestaan niet.
     Forceer `target.schema` (= lakehouse-naam).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if target.type == 'fabricspark' -%}
        {{ target.schema }}
    {%- elif target.type in ('databricks', 'spark') -%}
        {# Map Trino's catalog-naam (silver/gold) naar een UC schema. #}
        {%- set db_hint = node.config.database if node and node.config and node.config.database else 'silver' -%}
        {%- if db_hint == 'gold' -%}
            gold
        {%- else -%}
            silver
        {%- endif -%}
    {%- elif custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
