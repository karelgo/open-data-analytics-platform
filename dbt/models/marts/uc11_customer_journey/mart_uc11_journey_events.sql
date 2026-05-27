{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- UC-11 — Integrale Klantreis (event-stream).
--
-- Eén rij per cliënt-gebeurtenis met een uniform schema over zeven domeinen.
-- Genereert een chronologische volgnummer per BSN (event_seq) zodat downstream
-- visualisaties en fase-reconstructie tegen een stabiele ordering kunnen werken.
--
-- OPA-policies maskeren `bsn`, `event_label`, `source_ref_id` per rol — zie
-- opa-policies-src/trino/trino-column-masks.rego.

with events as (
    select * from {{ ref('int_customer_journey_events') }}
),

ranked as (
    select
        bsn,
        event_ts,
        event_date,
        domein,
        event_type,
        event_label,
        event_status,
        regio_code,
        numeric_value,
        source_ref_id,
        row_number() over (
            partition by bsn
            order by event_ts asc, domein asc, event_type asc
        ) as event_seq
    from events
)

select
    bsn,
    event_seq,
    event_ts,
    event_date,
    domein,
    event_type,
    event_label,
    event_status,
    regio_code,
    numeric_value,
    source_ref_id
from ranked
