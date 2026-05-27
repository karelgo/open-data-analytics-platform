{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-12 — Service-breakdown per regio × environment.
--
-- Eén rij per (billing_month × service_name × region × environment). Voedt
-- de "spend per service / per regio" pie-charts en de dist_bar drill-downs in
-- het UC-12 dashboard. `tag_environment` valt terug op 'unknown' zodat rijen
-- zonder tag niet from the dashboard verdwijnen.

with src as (
    select * from {{ ref('stg_focus_billing') }}
    where charge_category = 'Usage'   -- exclusief Purchases/Credits voor cleaner trend
)

select
    billing_month,
    provider,
    service_category,
    service_name,
    region,
    coalesce(tag_environment, 'unknown')              as environment,
    coalesce(tag_application, 'unknown')              as application,
    billing_currency,

    sum(effective_cost)                               as effective_cost,
    sum(billed_cost)                                  as billed_cost,
    sum(usage_quantity)                               as usage_quantity,
    count(distinct resource_id)                       as n_resources,
    count(*)                                          as n_charges
from src
group by
    billing_month, provider, service_category, service_name,
    region, coalesce(tag_environment, 'unknown'),
    coalesce(tag_application, 'unknown'), billing_currency
