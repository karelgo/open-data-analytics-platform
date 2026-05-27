{{ config(materialized='view') }}

-- FOCUS billing — CSV-batch bron (FinOps Open Cost and Usage Specification).
--
-- Normalisatie t.o.v. bronze.finops.focus_billing:
--   - PascalCase kolommen → snake_case
--   - Provider lowercased voor stabiele group-by
--   - Afgeleide `billing_month` = date_trunc('month', BillingPeriodStart);
--     dit is de natuurlijke aggregatie-grain voor alle UC-12 marts.
--   - `tags` blijft raw JSON-string; veel-gebruikte sleutels worden hier
--     uitgepakt naar eigen kolommen (environment, application, cost_center)
--     zodat marts geen json_extract hoeven te doen.
--   - oci_* kolommen passeren ongewijzigd (mogen null zijn voor non-OCI).

with src as (
    select * from {{ source('bronze', 'focus_billing') }}
)

select
    -- Identifiers
    BillingAccountId                                  as billing_account_id,
    BillingAccountName                                as billing_account_name,
    SubAccountId                                      as sub_account_id,
    SubAccountName                                    as sub_account_name,

    -- Periode
    BillingPeriodStart                                as billing_period_start,
    BillingPeriodEnd                                  as billing_period_end,
    ChargePeriodStart                                 as charge_period_start,
    ChargePeriodEnd                                   as charge_period_end,
    cast(date_trunc('month', BillingPeriodStart) as date) as billing_month,

    -- Charge-classificatie
    ChargeCategory                                    as charge_category,
    ChargeSubcategory                                 as charge_subcategory,
    ChargeDescription                                 as charge_description,
    ChargeFrequency                                   as charge_frequency,

    -- Kosten + valuta
    BillingCurrency                                   as billing_currency,
    BilledCost                                        as billed_cost,
    EffectiveCost                                     as effective_cost,
    ListCost                                          as list_cost,
    ListUnitPrice                                     as list_unit_price,
    -- Savings = list - effective; negatief betekent extra kosten t.o.v. lijst.
    coalesce(ListCost, EffectiveCost) - EffectiveCost as savings_amount,

    -- Pricing + kwantiteit
    PricingCategory                                   as pricing_category,
    PricingQuantity                                   as pricing_quantity,
    PricingUnit                                       as pricing_unit,
    UsageQuantity                                     as usage_quantity,
    UsageUnit                                         as usage_unit,

    -- Commitment / discount
    CommitmentDiscountCategory                        as commitment_discount_category,
    CommitmentDiscountId                              as commitment_discount_id,
    CommitmentDiscountName                            as commitment_discount_name,
    CommitmentDiscountType                            as commitment_discount_type,

    -- Provider + service
    lower(Provider)                                   as provider,
    Publisher                                         as publisher,
    InvoiceIssuer                                     as invoice_issuer,
    ServiceCategory                                   as service_category,
    ServiceName                                       as service_name,
    SkuId                                             as sku_id,
    SkuPriceId                                        as sku_price_id,

    -- Resource
    ResourceId                                        as resource_id,
    ResourceName                                      as resource_name,
    ResourceType                                      as resource_type,
    Region                                            as region,
    AvailabilityZone                                  as availability_zone,

    -- Tags — raw JSON + drie uitgepakte sleutels voor snelle filters in marts.
    Tags                                              as tags_raw,
    json_extract_scalar(Tags, '$.environment')        as tag_environment,
    json_extract_scalar(Tags, '$.application')        as tag_application,
    json_extract_scalar(Tags, '$.cost_center')        as tag_cost_center,

    -- OCI vendor-extensies — passeren ongewijzigd
    oci_ReferenceNumber                               as oci_reference_number,
    oci_CompartmentId                                 as oci_compartment_id,
    oci_CompartmentName                               as oci_compartment_name,
    oci_OverageFlag                                   as oci_overage_flag,
    oci_UnitPriceOverage                              as oci_unit_price_overage,
    oci_BilledQuantityOverage                         as oci_billed_quantity_overage,
    oci_CostOverage                                   as oci_cost_overage,
    oci_AttributedUsage                               as oci_attributed_usage,
    oci_AttributedCost                                as oci_attributed_cost,
    oci_BackReferenceNumber                           as oci_back_reference_number,

    -- Audit-velden uit bronze
    ingestion_ts,
    source_file,
    event_date
from src
