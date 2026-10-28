{{ config(properties=job_market_properties('mart_job_geography')) }}
select snapshot_date, domain, city, province, is_synthetic,
  count(*) as observed_jobs, count(distinct company) as hiring_companies
from {{ ref('int_job_snapshots') }} cross join unnest(domains) as d(domain)
group by 1, 2, 3, 4, 5
