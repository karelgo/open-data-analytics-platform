{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-01 — WIA Funnel daily.
-- Dagelijks aggregaat van WIA-request × status × regio × onderdeel.
-- Geen PII; sturingsinformatie voor RvB/managers.

with request as (
    select
        aanvraag_datum,
        regio_code,
        onderdeel,
        status,
        arbeidsongeschikt_pct
    from {{ ref('stg_claim_application') }}
)

select
    aanvraag_datum,
    regio_code,
    onderdeel,
    status,
    count(*)                                          as n_request,
    avg(arbeidsongeschikt_pct)                        as gemid_ao_pct,
    count(*) filter (where status = 'IN_BEHANDELING') as n_in_behandeling,
    count(*) filter (where status in ('TOEGEKEND_WGA', 'TOEGEKEND_IVA')) as n_toegekend,
    count(*) filter (where status = 'AFGEWEZEN')      as n_afgewezen
from request
group by aanvraag_datum, regio_code, onderdeel, status
