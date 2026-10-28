{{ config(properties=job_market_properties('mart_job_demand_daily')) }}
select snapshot_date, domain, is_synthetic,
  count(*) as observed_jobs,
  count_if(first_seen_date = snapshot_date) as first_observed_jobs,
  count(distinct company) as hiring_companies,
  count_if(work_mode = 'remote') as remote_jobs,
  count_if(work_mode = 'hybrid') as hybrid_jobs
from {{ ref('int_job_snapshots') }} cross join unnest(domains) as d(domain)
group by 1, 2, 3
