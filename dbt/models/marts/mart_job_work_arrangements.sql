{{ config(properties=job_market_properties('mart_job_work_arrangements')) }}
select snapshot_date, domain, work_mode, employment_type,
  contract_type, seniority, language, education, is_synthetic,
  count(*) as observed_jobs, avg(hours_min) as avg_hours_min,
  avg(hours_max) as avg_hours_max
from {{ ref('int_job_snapshots') }} cross join unnest(domains) as d(domain)
group by 1, 2, 3, 4, 5, 6, 7, 8, 9
