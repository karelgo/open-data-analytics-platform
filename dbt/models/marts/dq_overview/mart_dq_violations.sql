{{ config(
    materialized='table',
    properties=table_format_properties()
) }}

-- Cross-UC DQ-violations: 1 rij per (use_case × check), live geteld
-- on the gold-marts. Bron for the Superset "Datakwaliteit per UC"-
-- dashboard. Houdt dezelfde semantiek aan als de dbt-tests in
-- _uc*.yml; verschil: hier gematerialiseerd zodat een dashboard
-- continu kan tonen zonder de test-runner aan te roepen.
--
-- severity:
--   critical -> integriteits-fout (PII-uniek, BSN-validiteit, FK)
--   high     -> domein-violatie (out-of-range, nulls op kritisch veld)
--   medium   -> inhoudelijke afwijking (waarschuwing)

with uc01_checks as (
    select 'uc01' as uc_code, 'WIA Funnel' as uc_name,
           'aanvraag_datum_not_null' as check_name, 'high' as severity,
           count(*) filter (where aanvraag_datum is null) as n_violations,
           count(*) as n_records
    from {{ ref('mart_uc01_claims_funnel_daily') }}
    union all
    select 'uc01', 'WIA Funnel', 'status_not_null', 'high',
           count(*) filter (where status is null), count(*)
    from {{ ref('mart_uc01_claims_funnel_daily') }}
    union all
    select 'uc01', 'WIA Funnel', 'n_request_non_negative', 'high',
           count(*) filter (where n_request < 0), count(*)
    from {{ ref('mart_uc01_claims_funnel_daily') }}
    union all
    select 'uc01', 'WIA Funnel', 'onderdeel_in_WGA_IVA', 'medium',
           count(*) filter (where onderdeel not in ('WGA', 'IVA')), count(*)
    from {{ ref('mart_uc01_claims_funnel_daily') }}
),

uc04_checks as (
    select 'uc04' as uc_code, 'TW Eligibility' as uc_name,
           'bsn_not_null' as check_name, 'critical' as severity,
           count(*) filter (where bsn is null) as n_violations,
           count(*) as n_records
    from {{ ref('mart_uc04_eligibility_outreach') }}
    union all
    select 'uc04', 'TW Eligibility', 'inkomen_not_null', 'high',
           count(*) filter (where inkomen_maand_eur is null), count(*)
    from {{ ref('mart_uc04_eligibility_outreach') }}
    union all
    select 'uc04', 'TW Eligibility', 'gat_per_maand_non_negative', 'high',
           count(*) filter (where gat_per_maand < 0), count(*)
    from {{ ref('mart_uc04_eligibility_outreach') }}
),

uc05_checks as (
    select 'uc05' as uc_code, 'Client 360' as uc_name,
           'bsn_not_null' as check_name, 'critical' as severity,
           count(*) filter (where bsn is null) as n_violations,
           count(*) as n_records
    from {{ ref('mart_uc05_customer_360') }}
    union all
    select 'uc05', 'Client 360', 'bsn_unique', 'critical',
           count(*) - count(distinct bsn), count(*)
    from {{ ref('mart_uc05_customer_360') }}
    union all
    select 'uc05', 'Client 360', 'voornaam_not_null', 'high',
           count(*) filter (where voornaam is null), count(*)
    from {{ ref('mart_uc05_customer_360') }}
    union all
    select 'uc05', 'Client 360', 'geslacht_in_M_V_X', 'medium',
           count(*) filter (where geslacht not in ('M', 'V', 'X')), count(*)
    from {{ ref('mart_uc05_customer_360') }}
),

uc06_checks as (
    select 'uc06' as uc_code, 'Cost forecast' as uc_name,
           'jaar_in_2026_2030' as check_name, 'high' as severity,
           count(*) filter (where jaar < 2026 or jaar > 2030) as n_violations,
           count(*) as n_records
    from {{ ref('mart_uc06_cost_5y') }}
    union all
    select 'uc06', 'Cost forecast', 'maand_in_1_12', 'high',
           count(*) filter (where maand < 1 or maand > 12), count(*)
    from {{ ref('mart_uc06_cost_5y') }}
),

uc07_checks as (
    -- Hergebruikt het bestaande UC-07 DQ-dagrapport. Drempel "0"
    -- voor BSN-buiten-test-bereik komt uit _uc07.yml accepted_range.
    select 'uc07' as uc_code, 'DQ Polisadm' as uc_name,
           'bsn_buiten_test_bereik' as check_name, 'critical' as severity,
           coalesce(sum(n_bsn_buiten_test_bereik), 0) as n_violations,
           coalesce(sum(n_ikvs), 0) as n_records
    from {{ ref('mart_uc07_dq_dagrapport') }}
    union all
    select 'uc07', 'DQ Polisadm', 'lh_format_fout', 'high',
           coalesce(sum(n_lh_format_fout), 0),
           coalesce(sum(n_ikvs), 0)
    from {{ ref('mart_uc07_dq_dagrapport') }}
    union all
    select 'uc07', 'DQ Polisadm', 'loon_null', 'medium',
           coalesce(sum(n_loon_null), 0),
           coalesce(sum(n_ikvs), 0)
    from {{ ref('mart_uc07_dq_dagrapport') }}
    union all
    select 'uc07', 'DQ Polisadm', 'loon_boven_250k', 'medium',
           coalesce(sum(n_loon_boven_250k), 0),
           coalesce(sum(n_ikvs), 0)
    from {{ ref('mart_uc07_dq_dagrapport') }}
),

uc09_checks as (
    select 'uc09' as uc_code, 'Reint Effect' as uc_name,
           'bsn_pseudo_not_null' as check_name, 'critical' as severity,
           count(*) filter (where bsn_pseudo is null) as n_violations,
           count(*) as n_records
    from {{ ref('mart_uc09_effect_panel') }}
    union all
    select 'uc09', 'Reint Effect', 'bsn_pseudo_unique', 'critical',
           count(*) - count(distinct bsn_pseudo), count(*)
    from {{ ref('mart_uc09_effect_panel') }}
    union all
    select 'uc09', 'Reint Effect', 'leeftijd_in_18_100', 'high',
           count(*) filter (where leeftijd < 18 or leeftijd > 100), count(*)
    from {{ ref('mart_uc09_effect_panel') }}
    union all
    select 'uc09', 'Reint Effect', 'huidige_status_in_set', 'medium',
           count(*) filter (where huidige_status not in ('werkend', 'WW', 'WIA', 'overig')), count(*)
    from {{ ref('mart_uc09_effect_panel') }}
),

uc_customer_satisfaction_checks as (
    select 'uc_customer_satisfaction' as uc_code, 'Klanttevredenheid' as uc_name,
           'maand_not_null' as check_name, 'high' as severity,
           count(*) filter (where maand is null) as n_violations,
           count(*) as n_records
    from {{ ref('mart_uc_customer_satisfaction_kanaal_maand') }}
    union all
    select 'uc_customer_satisfaction', 'Klanttevredenheid', 'kanaal_not_null', 'high',
           count(*) filter (where kanaal is null), count(*)
    from {{ ref('mart_uc_customer_satisfaction_kanaal_maand') }}
    union all
    select 'uc_customer_satisfaction', 'Klanttevredenheid', 'n_respondenten_min_1', 'high',
           count(*) filter (where n_respondenten < 1), count(*)
    from {{ ref('mart_uc_customer_satisfaction_kanaal_maand') }}
    union all
    select 'uc_customer_satisfaction', 'Klanttevredenheid', 'gemid_score_in_1_5', 'high',
           count(*) filter (where gemid_score_gewogen < 1 or gemid_score_gewogen > 5), count(*)
    from {{ ref('mart_uc_customer_satisfaction_kanaal_maand') }}
)

select * from uc01_checks
union all select * from uc04_checks
union all select * from uc05_checks
union all select * from uc06_checks
union all select * from uc07_checks
union all select * from uc09_checks
union all select * from uc_customer_satisfaction_checks
