{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-07 — Datakwaliteit polisadministratie, dagrapport.
-- Aggregeert tellertjes per ingestiondag for the DQ-steward.

with ikv as (
    select
        event_date,
        bsn,
        lh_nummer,
        loon_bruto_jaar,
        is_lopend
    from {{ ref('stg_policy_holders') }}
)

select
    event_date as rapport_datum,
    count(*)                                                    as n_ikvs,
    count(distinct bsn)                                         as n_unieke_bsns,
    count(*) filter (where is_lopend)                           as n_lopend,
    count(*) filter (where not regexp_like(bsn, '^9[0-9]{8}$')) as n_bsn_buiten_test_bereik,
    count(*) filter (where loon_bruto_jaar is null)             as n_loon_null,
    count(*) filter (where loon_bruto_jaar > 250000)            as n_loon_boven_250k,
    count(*) filter (where not regexp_like(lh_nummer, '^[0-9]{9}L[0-9]{2}$')) as n_lh_format_fout
from ikv
group by event_date
