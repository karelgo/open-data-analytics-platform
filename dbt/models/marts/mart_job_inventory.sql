{{ config(properties=job_market_properties('mart_job_inventory')) }}
select * from {{ ref('int_job_snapshots') }}
where snapshot_date = (select max(snapshot_date) from {{ ref('int_job_snapshots') }})
