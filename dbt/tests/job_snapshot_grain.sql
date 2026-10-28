select snapshot_date, duplicate_group_id, count(*) as n
from {{ ref('int_job_snapshots') }} group by 1, 2 having count(*) > 1
