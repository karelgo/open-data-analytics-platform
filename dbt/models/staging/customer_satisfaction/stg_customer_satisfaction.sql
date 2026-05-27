{{ config(materialized='view') }}

-- Klanttevredenheid — CSV-batch bron (handmatige upload).
-- Anders dan envelope-bronnen leest deze direct kolommen uit bronze.
-- Schoonmaak hier: trim varchar, lowercase kanaal/doelgroep voor consistentie.

with src as (
    select
        meting_datum,
        kanaal,
        doelgroep,
        score,
        n_respondenten,
        opmerking,
        ingestion_ts,
        source_file,
        event_date
    from {{ source('bronze', 'customer_satisfaction') }}
)

select
    meting_datum,
    lower(trim(kanaal))                  as kanaal,
    lower(trim(doelgroep))               as doelgroep,
    score,
    n_respondenten,
    nullif(trim(opmerking), '')          as opmerking,
    ingestion_ts,
    source_file,
    event_date
from src
