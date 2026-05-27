{{ config(materialized='view') }}

-- Aggregeert maandinkomen per BSN voor UC-04 (TW-eligibility check).
-- Plaats: silver.intermediate.int_huishouden_inkomen

with ikv as (
    select
        bsn,
        sum(loon_bruto_jaar) as totaal_jaar
    from {{ ref('stg_policy_holders') }}
    where is_lopend = true
    group by bsn
)

select
    bsn,
    coalesce(totaal_jaar, 0)               as inkomen_jaar_eur,
    coalesce(totaal_jaar, 0) / 12.0        as inkomen_maand_eur
from ikv
