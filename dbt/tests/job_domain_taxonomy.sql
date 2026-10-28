select job_id, snapshot_date, domain
from {{ ref('stg_job_observations') }} cross join unnest(domains) as d(domain)
where domain not in ('data', 'cloud', 'sap', 'ai', 'software', 'security')
