{{ config(materialized='view', tags=['intermediate']) }}

-- Pseudo-identifier voor downstream-marts die geen ruwe BSN nodig hebben.
-- Gebruikt de centrale `pseudonymize`-macro (SHA-256 + zout) — production zou
-- HSM-gestuurde tokenisatie + per-cliënt-zout gebruiken.
--
-- Improvements #7: macro daadwerkelijk toepassen.

with src as (
    select * from {{ ref('stg_persons') }}
)

select
    bsn,
    {{ pseudonymize('bsn') }}      as bsn_pseudo,
    voornaam,
    achternaam,
    geslacht,
    birth_date,
    -- Voor rapportages die alleen leeftijdsbereik nodig hebben — geen exact dob.
    date_diff('year', birth_date, current_date) as leeftijd,
    cast(date_trunc('year', birth_date) as date) as geboortejaar,
    woonplaats,
    postcode,
    nationaliteit
from src
