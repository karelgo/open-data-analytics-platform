-- Geography and work breakdowns must conserve each daily domain's demand.
with geography as (
  select snapshot_date, domain, is_synthetic, sum(observed_jobs) as n
  from {{ ref('mart_job_geography') }} group by 1, 2, 3
), arrangements as (
  select snapshot_date, domain, is_synthetic, sum(observed_jobs) as n
  from {{ ref('mart_job_work_arrangements') }} group by 1, 2, 3
)
select d.snapshot_date, d.domain
from {{ ref('mart_job_demand_daily') }} d
left join geography g using (snapshot_date, domain, is_synthetic)
left join arrangements a using (snapshot_date, domain, is_synthetic)
where d.observed_jobs <> coalesce(g.n, 0) or d.observed_jobs <> coalesce(a.n, 0)
  or d.first_observed_jobs > d.observed_jobs
  or d.remote_jobs > d.observed_jobs or d.hybrid_jobs > d.observed_jobs
  or d.hiring_companies > d.observed_jobs
