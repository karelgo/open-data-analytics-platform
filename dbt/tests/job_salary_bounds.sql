select job_id, snapshot_date from {{ ref('stg_job_observations') }}
where salary_min < 0 or salary_max < salary_min
  or salary_year_min < 0 or salary_year_max < salary_year_min
  or (salary_year_min is not null and (salary_currency <> 'EUR' or salary_period not in ('year', 'month')))
  or (salary_currency = 'EUR' and salary_period = 'month'
      and (abs(salary_year_min - salary_min * 12) > 0.01
           or abs(salary_year_max - salary_max * 12) > 0.01))
  or (salary_currency = 'EUR' and salary_period = 'year'
      and (abs(salary_year_min - salary_min) > 0.01
           or abs(salary_year_max - salary_max) > 0.01))
