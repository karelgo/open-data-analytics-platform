{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-05 — 360°-cliëntbeeld.
-- Eén rij per BSN; OPA-policies in fase 9 maskeren kolommen per rol.
-- Voor de smoke-test bevatten we alle kolommen; OPA filtert at-query-time.

with persona as (
    select * from {{ ref('stg_persons') }}
),
ikv_lopend as (
    select
        bsn,
        count(*)                              as n_dienstverbanden_lopend,
        sum(loon_bruto_jaar)                  as totaal_loon_jaar,
        max(aanvang_dienstverband)            as laatste_dienstverband_aanvang
    from {{ ref('stg_policy_holders') }}
    where is_lopend = true
    group by bsn
),
ww_status as (
    select
        bsn,
        count(*) filter (where status in ('TOEGEKEND', 'IN_BEHANDELING'))  as n_lopende_ww
    from {{ ref('stg_service_request_application') }}
    group by bsn
),
wia_status as (
    select
        bsn,
        max(arbeidsongeschikt_pct) as max_ao_pct,
        count(*) filter (where status in ('TOEGEKEND_WGA','TOEGEKEND_IVA')) as n_lopende_wia
    from {{ ref('stg_claim_application') }}
    group by bsn
),
crm_recent as (
    select
        bsn,
        count(*) as n_contacts_30d
    from {{ ref('stg_customer_interaction') }}
    where contact_ts >= current_timestamp - interval '30' day
    group by bsn
)

select
    p.bsn,
    p.voornaam,
    p.achternaam,
    p.geslacht,
    p.birth_date,
    p.straat,
    p.huisnummer,
    p.postcode,
    p.woonplaats,
    coalesce(i.n_dienstverbanden_lopend, 0)  as n_dienstverbanden_lopend,
    coalesce(i.totaal_loon_jaar, 0)          as totaal_loon_jaar,
    coalesce(w.n_lopende_ww, 0)              as n_lopende_ww,
    coalesce(a.n_lopende_wia, 0)             as n_lopende_wia,
    a.max_ao_pct,
    coalesce(c.n_contacts_30d, 0)            as n_customer interactionen_30d
from persona p
left join ikv_lopend i  on p.bsn = i.bsn
left join ww_status  w  on p.bsn = w.bsn
left join wia_status a  on p.bsn = a.bsn
left join crm_recent c  on p.bsn = c.bsn
