-- Source observations retain every board's provenance; dates are collection dates.
select
  job_id, source, source_job_id, canonical_url, duplicate_group_id,
  cast(snapshot_date as date) as snapshot_date,
  try(from_iso8601_timestamp(observed_at)) as observed_at,
  title, company, city, province, country_code, latitude, longitude,
  description_text, domains, skills, seniority, employment_type, contract_type,
  work_mode, hours_min, hours_max, salary_min, salary_max, salary_currency,
  salary_period, salary_is_estimated, salary_year_min, salary_year_max,
  language, education,
  try(from_iso8601_timestamp(published_at)) as published_at,
  try(from_iso8601_timestamp(expires_at)) as expires_at,
  is_synthetic
from {{ source('job_market', 'observations') }}
where country_code = 'NL'
