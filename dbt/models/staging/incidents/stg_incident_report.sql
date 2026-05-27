{{ config(materialized='view') }}

with src as (
    select payload, source_ts, event_date
    from {{ source('bronze', 'incident_report') }}
)

select
    json_extract_scalar(payload, '$.payload.incident_id')              as incident_id,
    json_extract_scalar(payload, '$.payload.bsn')                     as bsn,
    cast(json_extract_scalar(payload, '$.payload.eerste_ziektedag') as date) as eerste_ziektedag,
    cast(json_extract_scalar(payload, '$.payload.duur_dagen') as integer) as duur_dagen,
    source_ts                                                           as ingestion_source_ts,
    event_date
from src
