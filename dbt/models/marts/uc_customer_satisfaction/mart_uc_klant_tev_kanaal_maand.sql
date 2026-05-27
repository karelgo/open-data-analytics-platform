{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-klant-tev — customer_satisfaction per kanaal × maand.
-- Sturingsinformatie voor divisie_customer interaction; geen PII.
-- Aggregaten op maand-niveau zodat éénmalige uploads en periodieke uploads
-- consistent blijven aggregeren.

with src as (
    select
        date_trunc('month', meting_datum) as maand,
        kanaal,
        score,
        n_respondenten
    from {{ ref('stg_customer_satisfaction') }}
)

select
    maand,
    kanaal,
    sum(n_respondenten)                                                  as n_respondenten,
    -- Gewogen gemiddelde: score telt evenredig met n_respondenten in de meting.
    cast(sum(score * n_respondenten) as double) / sum(n_respondenten)    as gemid_score_gewogen,
    avg(score)                                                            as gemid_score_ongew,
    count(*)                                                              as n_metingen
from src
group by 1, 2
