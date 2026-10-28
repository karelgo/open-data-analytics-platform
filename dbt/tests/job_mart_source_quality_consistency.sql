select * from {{ ref('mart_job_source_quality') }}
where distinct_job_candidates > source_observations
  or salary_present > source_observations or skills_present > source_observations
  or estimated_salary_observations > source_observations
  or classified_observations > source_observations
  or province_present > source_observations
  or duplicate_observations <> source_observations - distinct_job_candidates
