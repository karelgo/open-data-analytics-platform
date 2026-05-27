-- Singular test: WW-risico-features bevatten geen "protected attributes"
-- (etniciteit, wijk-code, religie). Voor UC-03 hoog-risico-AI hard-rule.
--
-- Hier alleen op staging-niveau gevalideerd; UC-03-features-mart komt fase 9.
-- Faalt als er kolommen met deze namen voorkomen in stg_ww_*.

select 1
where exists (
    select column_name
    from information_schema.columns
    where table_catalog = 'silver'
      and table_schema  = 'service_requests'
      and lower(column_name) in ('etniciteit', 'wijk', 'wijkcode', 'wijk_code',
                                 'religie', 'land_van_herkomst')
)
