{{ config(properties=job_market_properties('mart_job_source_quality')) }}
select snapshot_date, source, is_synthetic,
  count(*) as source_observations,
  count(distinct duplicate_group_id) as distinct_job_candidates,
  count_if(salary_year_min is not null) as salary_present,
  count_if(salary_is_estimated) as estimated_salary_observations,
  count_if(province is not null) as province_present,
  count_if(cardinality(skills) > 0) as skills_present,
  count_if(cardinality(domains) > 0) as classified_observations,
  max(observed_at) as last_observed_at,
  count(*) - count(distinct duplicate_group_id) as duplicate_observations
from {{ ref('stg_job_observations') }} group by 1, 2, 3
