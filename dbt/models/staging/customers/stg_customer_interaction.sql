{{ config(materialized='view') }}

with src as (
    select payload, source_ts, event_date
    from {{ source('bronze', 'customer_interaction') }}
)

select
    json_extract_scalar(payload, '$.payload.contact_id')             as contact_id,
    json_extract_scalar(payload, '$.payload.bsn')                    as bsn,
    json_extract_scalar(payload, '$.payload.kanaal')                 as kanaal,
    json_extract_scalar(payload, '$.payload.onderwerp')              as onderwerp,
    -- ISO-8601 met `Z` (`2025-06-15T14:05:00Z`) is geen Trino cast-target.
    -- from_iso8601_timestamp() pakt het wel; resultaat is timestamp(3) with time zone.
    from_iso8601_timestamp(json_extract_scalar(payload, '$.payload.timestamp')) as contact_ts,
    cast(json_extract_scalar(payload, '$.payload.duur_seconden') as integer) as duur_seconden,
    source_ts                                                          as ingestion_source_ts,
    event_date
from src
