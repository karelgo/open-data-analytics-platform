-- Displayed salary summaries require a real sample and ordered EUR bounds.
select * from {{ ref('mart_job_salary') }}
where salary_sample_size <= 0 or salary_sample_size > observed_jobs
  or annual_min_eur < 0 or annual_max_eur < annual_min_eur
  or avg_annual_midpoint_eur not between annual_min_eur and annual_max_eur
  or median_annual_midpoint_eur not between annual_min_eur and annual_max_eur
