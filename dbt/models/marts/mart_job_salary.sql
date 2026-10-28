{{ config(properties=job_market_properties('mart_job_salary')) }}
select snapshot_date, domain, seniority, salary_is_estimated, is_synthetic,
  count(*) as observed_jobs,
  count(salary_year_min) as salary_sample_size,
  avg((salary_year_min + salary_year_max) / 2.0) as avg_annual_midpoint_eur,
  approx_percentile((salary_year_min + salary_year_max) / 2.0, 0.5) as median_annual_midpoint_eur,
  min(salary_year_min) as annual_min_eur, max(salary_year_max) as annual_max_eur
from {{ ref('int_job_snapshots') }} cross join unnest(domains) as d(domain)
where salary_currency = 'EUR' and salary_period in ('month', 'year')
  and salary_year_min is not null and salary_year_max is not null
group by 1, 2, 3, 4, 5
