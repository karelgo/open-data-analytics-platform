{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-06 — Cost forecast / claim_cost prognose, basis-projectie.
-- Vertrekt uit historische maand-aggregaten en lineair extrapoleert
-- naar 5 jaar vooruit per wet × regio.

with hist as (
    select
        jaar,
        maand,
        wet,
        regio_code,
        sum(uitbetaald_bruto_eur) as last_eur,
        sum(aantal_claim payouten)   as n_claim payouten
    from {{ ref('stg_finance_expense') }}
    group by jaar, maand, wet, regio_code
),
trend as (
    -- Eenvoudig: gemiddelde maandgroei per wet × regio over 36 mnd hist.
    select
        wet,
        regio_code,
        avg(last_eur)             as avg_maand_last,
        avg(n_claim payouten)        as avg_n_per_maand
    from hist
    group by wet, regio_code
),
projection as (
    select
        t.wet,
        t.regio_code,
        proj_jaar,
        proj_maand,
        cast(t.avg_maand_last as integer)  as last_eur_proj,
        cast(t.avg_n_per_maand as integer) as n_claim payouten_proj
    from trend t
    cross join unnest(sequence(2026, 2030)) as proj(proj_jaar)
    cross join unnest(sequence(1, 12))      as m(proj_maand)
)
select
    proj_jaar  as jaar,
    proj_maand as maand,
    wet,
    regio_code,
    last_eur_proj      as uitbetaald_bruto_eur_projection,
    n_claim payouten_proj as aantal_claim payouten_projection,
    'baseline'         as scenario_id
from projection
