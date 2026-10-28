-- Same normalized employer/title/city identifies conservative duplicate candidates.
-- Prefer reported salary evidence, then estimates, then missing salary. The
-- completeness score and final source-ID tie-break match the offline example.
{% set scalar_fields = [
    'job_id', 'source', 'source_job_id', 'canonical_url', 'duplicate_group_id',
    'snapshot_date', 'observed_at', 'title', 'company', 'city',
    'province', 'country_code', 'latitude', 'longitude', 'description_text',
    'seniority', 'employment_type', 'contract_type', 'work_mode', 'hours_min',
    'hours_max', 'salary_min', 'salary_max', 'salary_currency', 'salary_period',
    'salary_is_estimated', 'salary_year_min', 'salary_year_max', 'language', 'education',
    'published_at', 'expires_at', 'is_synthetic'
] %}
with evidence as (
  select *,
    case
      when (salary_min is not null or salary_max is not null)
           and not salary_is_estimated then 2
      when salary_min is not null or salary_max is not null then 1
      else 0
    end as salary_evidence_rank,
    {% for field in scalar_fields %}
      case when {{ field }} is not null then 1 else 0 end +
    {% endfor %}
      case when cardinality(domains) > 0 then 1 else 0 end +
      case when cardinality(skills) > 0 then 1 else 0 end as completeness_score
  from {{ ref('stg_job_observations') }}
), observations as (
  select *, row_number() over (
    partition by snapshot_date, duplicate_group_id
    order by salary_evidence_rank desc, completeness_score desc, job_id desc
  ) as chosen
  from evidence
), provenance as (
  select snapshot_date, duplicate_group_id,
    array_sort(array_distinct(array_agg(source))) as sources,
    array_sort(array_distinct(array_agg(canonical_url))) as source_urls,
    array_sort(array_distinct(flatten(array_agg(domains)))) as all_domains,
    array_sort(array_distinct(flatten(array_agg(skills)))) as all_skills,
    count(*) as source_observation_count,
    min(observed_at) as first_observed_at_in_snapshot
  from observations group by 1, 2
)
select
  {% for field in scalar_fields %}
    o.{{ field }},
  {% endfor %}
  p.all_domains as domains, p.all_skills as skills,
  p.sources, p.source_urls, p.source_observation_count,
  p.first_observed_at_in_snapshot,
  min(o.snapshot_date) over(partition by o.duplicate_group_id) as first_seen_date
from observations o
join provenance p using (snapshot_date, duplicate_group_id)
where chosen = 1
