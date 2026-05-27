{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-04 — Proactieve TW-aanvulling (regel-gebaseerd, geen profilering).
-- Selecteer cliënten waarvoor maandinkomen onder TW-norm ligt.
-- Gebruikt seed `tw_normen_2026` voor drempels.
--
-- DEMO-versie: huishoud_type wordt niet uit BRP afgeleid; we matchen elke
-- persoon tegen de norm voor 'alleenstaand'. Productie zou BRP-spiegel
-- bevragen.

with personen as (
    select
        p.bsn,
        coalesce(i.inkomen_maand_eur, 0) as inkomen_maand_eur
    from {{ ref('stg_persons') }} p
    left join {{ ref('int_huishouden_inkomen') }} i on p.bsn = i.bsn
),
tw_norm as (
    select norm_per_maand_eur
    from {{ ref('tw_normen_2026') }}
    where huishoud_type = 'alleenstaand'
)
select
    p.bsn,
    p.inkomen_maand_eur,
    n.norm_per_maand_eur,
    n.norm_per_maand_eur - p.inkomen_maand_eur as gat_per_maand,
    'alleenstaand'                              as huishoud_type_aanname,
    'demo: huishoud_type via BRP-koppeling in productie' as toelichting,
    -- opt_out vlag voor OPA row-filter (rowFilters.rego). Default false;
    -- in productie gevuld vanuit cliënt-voorkeuren-DB.
    false                                        as opt_out
from personen p
cross join tw_norm n
where p.inkomen_maand_eur < n.norm_per_maand_eur
