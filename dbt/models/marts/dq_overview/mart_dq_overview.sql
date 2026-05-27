{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- Cross-UC DQ-overzicht: 1 rij per use-case met aggregate-cijfers.
-- Bron for the top-tiles van het Superset DQ-dashboard.
--
-- dq_score_pct = 100 - (n_violations / max(n_check_evaluations, 1) * 100)
-- waarbij n_check_evaluations = aantal records × aantal checks
-- (dus aantal pass+fail-evaluaties, niet aantal checks).

with per_uc as (
    select
        uc_code,
        uc_name,
        max(n_records)                                    as n_records,
        count(*)                                          as n_checks,
        sum(n_violations)                                 as n_violations,
        sum(case when severity = 'critical'
                 then n_violations else 0 end)            as n_violations_critical,
        sum(case when severity = 'high'
                 then n_violations else 0 end)            as n_violations_high,
        sum(case when severity = 'medium'
                 then n_violations else 0 end)            as n_violations_medium,
        sum(case when n_violations > 0 then 1 else 0 end) as n_failing_checks
    from {{ ref('mart_dq_violations') }}
    group by uc_code, uc_name
),

with_score as (
    select
        uc_code,
        uc_name,
        n_records,
        n_checks,
        n_violations,
        n_violations_critical,
        n_violations_high,
        n_violations_medium,
        n_failing_checks,
        n_checks - n_failing_checks                       as n_passing_checks,
        case
            when n_records * n_checks = 0 then 100.0
            else round(
                100.0 - (cast(n_violations as double)
                         / (n_records * n_checks)) * 100.0,
                2)
        end                                                as dq_score_pct
    from per_uc
)

select
    uc_code,
    uc_name,
    n_records,
    n_checks,
    n_passing_checks,
    n_failing_checks,
    n_violations,
    n_violations_critical,
    n_violations_high,
    n_violations_medium,
    dq_score_pct,
    case
        when n_violations_critical > 0 then 'rood'
        when n_violations_high > 0     then 'oranje'
        when n_violations_medium > 0   then 'geel'
        else                                'groen'
    end                                                    as dq_status
from with_score
