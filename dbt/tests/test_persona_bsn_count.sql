-- Singular test: minimaal 1 record in silver.persona — sanity-check
-- dat de bronze→silver pipeline ten minste iets oplevert.

select 1
where (select count(*) from {{ ref('stg_persons') }}) = 0
