{# Database resolutie per target:

   - trino: gebruik letterlijk `+database:` waarde uit het project
     (bv. `silver`, `gold` — Trino-catalogs).
   - databricks: Unity Catalog heeft één catalog per workspace-binding
     (bv. `databricks`). Negeer `+database:` uit dbt_project.yml
     (dat is een Trino-catalog-naam) en gebruik altijd `target.database`
     zodat alle layers in dezelfde UC catalog landen.
   - fabricspark: het Lakehouse heeft één database (= lakehouse-naam).
     Zelfde patroon als databricks — dbt-fabricspark forceert al
     target.database = lakehouse-naam in credentials.__post_init__.
#}
{% macro generate_database_name(custom_database_name=none, node=none) -%}
    {%- if target.type in ('fabricspark', 'databricks', 'spark') -%}
        {{ target.database }}
    {%- elif custom_database_name is none -%}
        {{ target.database }}
    {%- else -%}
        {{ custom_database_name | trim }}
    {%- endif -%}
{%- endmacro %}
