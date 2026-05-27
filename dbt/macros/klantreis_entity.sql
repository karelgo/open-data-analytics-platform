{# Target-aware relation resolver voor UC-11 silver-equivalent entities.

   Drie engines:
   - Trino:        `ref('stg_<name>')` — staging-view met JSON-extractie uit bronze.
   - Fabricspark:  `source('silver', <name>)` — flat Delta in Lakehouse (uc11_silver notebook).
   - Databricks:   `source('silver_uc', <name>)` — flat Delta in Unity Catalog
                   (uc11_silver notebook, schrijft naar databricks.silver.*).

   `name` is de entity-naam zonder prefix:
     - persona, policy_holders, service_request_application, incident_report,
       claim_application, eligibility_case, customer_interaction

   Hierdoor blijft `int_customer_journey_events.sql` één SQL-bestand dat
   onveranderd over engines portable is — de macro encapsuleert de
   engine-specifieke source/ref-keuze.
#}
{% macro klantreis_entity(name) -%}
    {%- if target.type == 'fabricspark' -%}
        {{ source('silver', name) }}
    {%- elif target.type in ('databricks', 'spark') -%}
        {{ source('silver_uc', name) }}
    {%- else -%}
        {{ ref('stg_' ~ name) }}
    {%- endif -%}
{%- endmacro %}
