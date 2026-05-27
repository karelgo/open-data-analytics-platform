{{ config(
    materialized='table',
    database='silver',
    schema='sandbox_uc09',
    properties=table_format_properties()
) }}

-- UC-09 — Reintegration effectmeting (sandbox-panel).
-- 100% gepseudonimiseerd: geen ruwe BSN beschikbaar voor researcher-rol.
-- OPA `trino-row-filters.rego` filtert sandbox-records nogmaals op
-- `bsn_pseudo IS NOT NULL` als defensieve dubbel-check.
--
-- Improvements #7: pseudonymize macro daadwerkelijk gebruikt.

with persona as (
    select bsn, bsn_pseudo, leeftijd, geslacht
    from {{ ref('int_persona_pseudonymized') }}
),

ww as (
    select
        bsn,
        count(*)                                          as n_ww_request,
        max(aanvraag_datum)                               as laatste_ww_datum,
        sum(case when status = 'TOEGEKEND' then 1 else 0 end) as ww_toegekend
    from {{ ref('stg_service_request_application') }}
    group by bsn
),

wia as (
    select
        bsn,
        count(*)                       as n_wia_request,
        max(arbeidsongeschikt_pct)     as max_ao_pct
    from {{ ref('stg_claim_application') }}
    group by bsn
),

werk_status as (
    select
        bsn,
        count(*) filter (where is_lopend = true)  as dienstverbanden_lopend,
        sum(loon_bruto_jaar) filter (where is_lopend = true) as loon_jaar_lopend
    from {{ ref('stg_policy_holders') }}
    group by bsn
)

select
    p.bsn_pseudo,                                                 -- ENIGE id-veld in panel
    p.leeftijd,
    p.geslacht,
    coalesce(w.n_ww_request, 0)             as n_ww_request,
    coalesce(w.ww_toegekend, 0) > 0           as ooit_ww_toegekend,
    coalesce(a.n_wia_request, 0)            as n_wia_request,
    a.max_ao_pct,
    coalesce(s.dienstverbanden_lopend, 0)     as dienstverbanden_lopend,
    coalesce(s.loon_jaar_lopend, 0)           as loon_jaar_lopend,
    case
        when coalesce(s.dienstverbanden_lopend, 0) > 0 then 'werkend'
        when coalesce(w.n_ww_request, 0) > 0          then 'WW'
        when coalesce(a.n_wia_request, 0) > 0         then 'WIA'
        else 'overig'
    end                                       as huidige_status
from persona p
left join ww          w using (bsn)
left join wia         a using (bsn)
left join werk_status s using (bsn)
