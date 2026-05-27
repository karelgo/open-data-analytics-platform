{{ config(materialized='view') }}

with src as (
    select payload, source_ts, event_date
    from {{ source('bronze', 'policy_holders') }}
)

select
    json_extract_scalar(payload, '$.payload.ikv_id')                as ikv_id,
    json_extract_scalar(payload, '$.payload.bsn')                   as bsn,
    json_extract_scalar(payload, '$.payload.lh_nummer')             as lh_nummer,
    json_extract_scalar(payload, '$.payload.werkgever_naam')        as werkgever_naam,
    cast(json_extract_scalar(payload, '$.payload.aanvang_dienstverband') as date) as aanvang_dienstverband,
    cast(json_extract_scalar(payload, '$.payload.einde_dienstverband') as date)   as einde_dienstverband,
    cast(json_extract_scalar(payload, '$.payload.loon_bruto_jaar') as integer)    as loon_bruto_jaar,
    case
        when json_extract_scalar(payload, '$.payload.einde_dienstverband') is null
        then true
        else false
    end                                                              as is_lopend,
    source_ts                                                         as ingestion_source_ts,
    event_date
from src
