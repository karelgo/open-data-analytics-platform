{{ config(properties=job_market_properties('mart_job_skills')) }}
select snapshot_date, domain, skill, is_synthetic, count(*) as observed_jobs
from {{ ref('int_job_snapshots') }}
cross join unnest(domains) as d(domain)
cross join unnest(skills) as s(skill)
group by 1, 2, 3, 4
