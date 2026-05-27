{{ config(materialized='view') }}

with src as (
    select payload, source_ts, event_date
    from {{ source('bronze', 'finance_expense') }}
)

select
    cast(json_extract_scalar(payload, '$.payload.jaar') as integer)            as jaar,
    cast(json_extract_scalar(payload, '$.payload.maand') as integer)           as maand,
    json_extract_scalar(payload, '$.payload.wet')                              as wet,
    json_extract_scalar(payload, '$.payload.regio_code')                       as regio_code,
    cast(json_extract_scalar(payload, '$.payload.uitbetaald_bruto_eur') as integer) as uitbetaald_bruto_eur,
    cast(json_extract_scalar(payload, '$.payload.aantal_uitkeringen') as integer)   as aantal_uitkeringen,
    source_ts                                                                    as ingestion_source_ts,
    event_date
from src
