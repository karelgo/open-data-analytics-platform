{{ config(materialized='view') }}

with src as (
    select payload, source_ts, event_date
    from {{ source('bronze', 'service_request_application') }}
)

select
    json_extract_scalar(payload, '$.payload.application_id')                  as application_id,
    json_extract_scalar(payload, '$.payload.bsn')                          as bsn,
    cast(json_extract_scalar(payload, '$.payload.aanvraag_datum') as date) as aanvraag_datum,
    cast(json_extract_scalar(payload, '$.payload.laatste_werkdag') as date) as laatste_werkdag,
    json_extract_scalar(payload, '$.payload.reden_einde_dienstverband')    as reden_einde_dienstverband,
    json_extract_scalar(payload, '$.payload.status')                       as status,
    source_ts                                                                as ingestion_source_ts,
    event_date
from src
