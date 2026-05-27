{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-06 — Scenario-resultaten.
-- Past scenario_inputs.csv parameters toe on the baseline-prognose.
-- Implementatie: declaratief — voor elk scenario een MERGE-achtige rule.

with baseline as (
    select * from {{ ref('mart_uc06_cost_5y') }}
),
sc as (
    select * from {{ ref('scenario_inputs') }}
)

-- Voor demo: drie scenario's hardcoded; production zou een policy-engine zijn.
select
    b.jaar,
    b.maand,
    b.wet,
    b.regio_code,
    case
        when sc.scenario_id = 'iva_afschaf_2027' and b.wet = 'WIA' and b.jaar >= 2027
            then 0
        when sc.scenario_id = 'ww_versoberen' and b.wet = 'WW'
            then cast(b.uitbetaald_bruto_eur_projection * 0.5 as integer)
        else b.uitbetaald_bruto_eur_projection
    end as uitbetaald_bruto_eur_projection,
    case
        when sc.scenario_id = 'iva_afschaf_2027' and b.wet = 'WIA' and b.jaar >= 2027
            then 0
        when sc.scenario_id = 'ww_versoberen' and b.wet = 'WW'
            then cast(b.aantal_claim payouten_projection * 0.5 as integer)
        else b.aantal_claim payouten_projection
    end as aantal_claim payouten_projection,
    sc.scenario_id
from baseline b
cross join sc
where sc.scenario_id in ('baseline', 'iva_afschaf_2027', 'ww_versoberen')
