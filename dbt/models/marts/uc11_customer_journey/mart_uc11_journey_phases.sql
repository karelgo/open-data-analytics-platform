{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-11 — Integrale Klantreis (fase-reconstructie).
--
-- Gaps-and-islands op `mart_uc11_journey_events`: voor elke cliënt de
-- chronologische reeks van fasen die zijn afgeleid uit fase-triggerende
-- events. Crm-contacten en de aanmaak-event triggeren géén fase-wissel
-- (carry-forward).
--
-- Output: één rij per (bsn × fase × periode). Een cliënt kan dezelfde fase
-- meerdere keren doorlopen (bv. werknemer → ziek → werknemer).

with src as (
    select * from {{ ref('mart_uc11_journey_events') }}
),

with_fase as (
    select
        bsn,
        event_seq,
        event_ts,
        event_type,
        event_status,
        case
            when event_type = 'polisadm.ikv.start'                      then 'werknemer'
            when event_type = 'polisadm.ikv.einde'                      then 'tussen_dienstverband'
            when event_type = 'zw.melding'                              then 'ziek'
            when event_type like 'ww.aanvraag.%'
                 and event_status in ('INGEDIEND', 'IN_BEHANDELING')    then 'service_request_application'
            when event_type = 'ww.aanvraag.toegekend'                   then 'ww_uitkering'
            when event_type = 'ww.aanvraag.afgewezen'                   then 'tussen_dienstverband'
            when event_type like 'wia.aanvraag.%'
                 and event_status in ('INGEDIEND', 'IN_BEHANDELING')    then 'wia_in_behandeling'
            when event_type = 'wia.aanvraag.toegekend_wga'              then 'wga'
            when event_type = 'wia.aanvraag.toegekend_iva'              then 'iva'
            when event_type = 'wia.aanvraag.afgewezen'                  then 'tussen_dienstverband'
            when event_type = 'wajong.dossier'                  then 'wajong_actief'
            else null   -- crm.contact.* en persoon.aangemaakt → geen fase-wissel
        end as fase
    from src
),

fase_events as (
    -- Alleen events die daadwerkelijk een fase initiëren.
    select * from with_fase where fase is not null
),

islands as (
    -- Gaps-and-islands: nieuwe island = fase wijzigt t.o.v. vorige rij.
    select
        bsn,
        event_seq,
        event_ts,
        fase,
        event_type as trigger_event_type,
        lag(fase) over (partition by bsn order by event_seq) as prev_fase
    from fase_events
),

starts as (
    select
        bsn,
        event_seq,
        event_ts as fase_start_ts,
        fase,
        trigger_event_type
    from islands
    where prev_fase is null or prev_fase != fase
),

bounded as (
    select
        bsn,
        row_number() over (partition by bsn order by fase_start_ts) as fase_volgnr,
        fase,
        trigger_event_type,
        fase_start_ts,
        lead(fase_start_ts) over (partition by bsn order by fase_start_ts) as fase_eind_ts
    from starts
)

select
    bsn,
    fase_volgnr,
    fase,
    trigger_event_type,
    fase_start_ts,
    fase_eind_ts,
    case
        when fase_eind_ts is null then null
        else {{ dbt.datediff('cast(fase_start_ts as date)',
                             'cast(fase_eind_ts as date)',
                             'day') }}
    end as duur_dagen,
    case when fase_eind_ts is null then true else false end as is_lopend
from bounded
