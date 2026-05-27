{{ config(materialized='view') }}

with src as (
    select payload, source_ts, event_date
    from {{ source('bronze', 'eligibility_case') }}
)

select
    json_extract_scalar(payload, '$.payload.case_id')              as case_id,
    json_extract_scalar(payload, '$.payload.bsn')                     as bsn,
    json_extract_scalar(payload, '$.payload.regime')                  as regime,
    json_extract_scalar(payload, '$.payload.arbeidsvermogen')         as arbeidsvermogen,
    cast(json_extract_scalar(payload, '$.payload.ingangsdatum') as date) as ingangsdatum,
    source_ts                                                           as ingestion_source_ts,
    event_date
from src
