select snapshot_date, job_id, count(*) as n
from {{ ref('stg_job_observations') }} group by 1, 2 having count(*) > 1
