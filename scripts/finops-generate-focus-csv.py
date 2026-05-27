#!/usr/bin/env python3
"""Genereer een synthetic FOCUS-billing CSV voor UC-12 testen.

Maakt een CSV die voldoet aan het schema in
platform/11-airflow/sources/focus.yml — bruikbaar voor end-to-end test
van de upload-flow (portal → MinIO → ingest_csv_focus → bronze → silver
→ gold → Superset).

Standaard: 3 maanden × 6 services × 4 regio's × meerdere resources →
~600 rijen, ~80 KB. Bedragen zijn synthetisch maar plausibel (compute
domineert, met committed-discounts en sporadische overages).

Gebruik:
    python3 scripts/finops-generate-focus-csv.py > /tmp/focus-test.csv
    # of:
    python3 scripts/finops-generate-focus-csv.py --output /tmp/focus-test.csv

SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal


FOCUS_COLUMNS = [
    "AvailabilityZone", "BilledCost", "BillingAccountId", "BillingAccountName",
    "BillingCurrency", "BillingPeriodEnd", "BillingPeriodStart", "ChargeCategory",
    "ChargeDescription", "ChargeFrequency", "ChargePeriodEnd", "ChargePeriodStart",
    "ChargeSubcategory", "CommitmentDiscountCategory", "CommitmentDiscountId",
    "CommitmentDiscountName", "CommitmentDiscountType", "EffectiveCost",
    "InvoiceIssuer", "ListCost", "ListUnitPrice", "PricingCategory",
    "PricingQuantity", "PricingUnit", "Provider", "Publisher", "Region",
    "ResourceId", "ResourceName", "ResourceType", "ServiceCategory",
    "ServiceName", "SkuId", "SkuPriceId", "SubAccountId", "SubAccountName",
    "Tags", "UsageQuantity", "UsageUnit",
    "oci_ReferenceNumber", "oci_CompartmentId", "oci_CompartmentName",
    "oci_OverageFlag", "oci_UnitPriceOverage", "oci_BilledQuantityOverage",
    "oci_CostOverage", "oci_AttributedUsage", "oci_AttributedCost",
    "oci_BackReferenceNumber",
]

# Services × eenheid × baseline unit-price (EUR). Compute domineert; storage en
# database zijn middelhoog; observability is klein; data-egress is grillig.
SERVICES = [
    # (ServiceCategory, ServiceName, ResourceType, PricingUnit, UsageUnit, unit_price)
    ("Compute",         "Compute - VM.Standard.E4",  "VirtualMachine",   "OCPU-Hour",   "OCPU-Hour",   0.025),
    ("Compute",         "Compute - VM.Standard.A1",  "VirtualMachine",   "OCPU-Hour",   "OCPU-Hour",   0.015),
    ("Storage",         "Block Volume - Balanced",   "BlockVolume",      "GB-Month",    "GB-Month",    0.0425),
    ("Storage",         "Object Storage - Standard", "Bucket",           "GB-Month",    "GB-Month",    0.0255),
    ("Databases",       "Autonomous Database - OLTP","Database",         "OCPU-Hour",   "OCPU-Hour",   1.3441),
    ("Networking",      "Data Egress - Internet",    "EgressGateway",    "GB",          "GB",          0.0085),
    ("AI and Machine Learning", "OCI Generative AI", "ModelEndpoint",    "Token",       "Token",       0.000002),
    ("Management and Governance", "Logging",         "LogGroup",         "GB-Month",    "GB-Month",    0.42),
]

REGIONS = [
    ("eu-amsterdam-1",  ["AD-1", "AD-2", "AD-3"]),
    ("eu-frankfurt-1",  ["AD-1", "AD-2", "AD-3"]),
    ("us-ashburn-1",    ["AD-1", "AD-2", "AD-3"]),
    ("uk-london-1",     ["AD-1", "AD-2", "AD-3"]),
]

COMPARTMENTS = [
    ("ocid1.compartment.prod",   "prod"),
    ("ocid1.compartment.acc",    "acc"),
    ("ocid1.compartment.test",   "test"),
    ("ocid1.compartment.shared", "shared"),
]

ENVIRONMENTS = ["prod", "acc", "test"]
APPLICATIONS = [
    "uc01-claims-funnel", "uc04-eligibility-outreach", "uc05-customer-360",
    "uc11-customer-journey", "platform-shared", "data-ingestion",
]
COST_CENTERS = ["FIN-BI-001", "FIN-PLATFORM-002", "FIN-AI-003", "FIN-DATA-004"]


def iso(dt: datetime) -> str:
    """ISO 8601 met Z-suffix — matcht FOCUS-spec en OCI-export."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def month_window(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def emit_row(writer: csv.DictWriter, rnd: random.Random, *,
             month_start: datetime, month_end: datetime,
             service: tuple, region_pair: tuple, compartment: tuple,
             environment: str, application: str, cost_center: str,
             resource_seq: int) -> None:
    """Schrijf één FOCUS-billing rij for a (service × region × resource)."""
    svc_cat, svc_name, res_type, pricing_unit, usage_unit, unit_price = service
    region, azs = region_pair
    az = rnd.choice(azs) if res_type == "VirtualMachine" else ""
    compartment_id, compartment_name = compartment

    # Charge-window: meestal volledige maand; soms (purchases) een korter venster.
    charge_start = month_start
    charge_end = month_end

    # Usage-volume varieert per service-categorie en environment.
    base_qty = {
        "Compute":   rnd.uniform(200, 4000),
        "Storage":   rnd.uniform(50, 5000),
        "Databases": rnd.uniform(100, 800),
        "Networking": rnd.uniform(20, 1500),
        "AI and Machine Learning": rnd.uniform(50_000, 5_000_000),
        "Management and Governance": rnd.uniform(5, 200),
    }[svc_cat]
    if environment != "prod":
        base_qty *= rnd.uniform(0.1, 0.4)   # non-prod = veel lager
    quantity = round(base_qty, 4)

    list_cost = Decimal(str(quantity)) * Decimal(str(unit_price))
    # ~40% van compute heeft committed discount (savings 20-35%); rest standard.
    if svc_cat == "Compute" and rnd.random() < 0.4:
        pricing_category = "Committed"
        discount_pct = Decimal(str(rnd.uniform(0.20, 0.35)))
        commitment_id = f"cd-{rnd.randint(1000, 9999)}"
        commitment_name = "Universal Credits 1Y"
        commitment_type = "Savings Plan"
        commitment_cat = "Spend"
    else:
        pricing_category = "Standard"
        discount_pct = Decimal("0")
        commitment_id = ""
        commitment_name = ""
        commitment_type = ""
        commitment_cat = ""

    effective_cost = (list_cost * (Decimal("1") - discount_pct)).quantize(Decimal("0.000001"))
    billed_cost = effective_cost   # geen separate negotiated rate in deze synth

    # Charge-categorie: 90% Usage, 5% Purchase (upfront committed), 5% Credit.
    roll = rnd.random()
    if roll < 0.05:
        charge_category = "Purchase"
        charge_frequency = "OneTime"
        charge_subcategory = "Reservation Fee"
    elif roll < 0.10:
        charge_category = "Credit"
        charge_frequency = "OneTime"
        charge_subcategory = "Promotional"
        billed_cost = -billed_cost
        effective_cost = -effective_cost
    else:
        charge_category = "Usage"
        charge_frequency = "Usage-Based"
        charge_subcategory = ""

    # OCI-overage: ~3% kans op overschrijding committed.
    overage_flag = ""
    unit_price_overage = ""
    billed_qty_overage = ""
    cost_overage = ""
    if pricing_category == "Committed" and rnd.random() < 0.03:
        overage_flag = "Y"
        unit_price_overage = f"{unit_price * 1.2:.8f}"
        overage_qty = round(quantity * rnd.uniform(0.05, 0.2), 4)
        billed_qty_overage = f"{overage_qty:.8f}"
        cost_overage = f"{overage_qty * unit_price * 1.2:.6f}"

    tags = json.dumps({
        "environment":  environment,
        "application":  application,
        "cost_center":  cost_center,
        "owner_team":   "platform team" if application == "platform-shared" else "data-team",
    }, separators=(",", ":"))

    resource_id = (
        f"ocid1.{res_type.lower()}.{region}.{compartment_name}."
        f"{application}-{resource_seq:03d}"
    )
    resource_name = f"{application}-{res_type[:3].lower()}-{resource_seq:03d}"

    ref_no = f"OCI-{month_start:%Y%m}-{rnd.randint(100_000, 999_999)}"

    writer.writerow({
        "AvailabilityZone":  az,
        "BilledCost":        f"{billed_cost:.6f}",
        "BillingAccountId":  "oci-acct-odap-001",
        "BillingAccountName":"Open Data & Analytics Platform — Master",
        "BillingCurrency":   "EUR",
        "BillingPeriodEnd":  iso(month_end),
        "BillingPeriodStart":iso(month_start),
        "ChargeCategory":    charge_category,
        "ChargeDescription": f"{svc_name} in {region}",
        "ChargeFrequency":   charge_frequency,
        "ChargePeriodEnd":   iso(charge_end),
        "ChargePeriodStart": iso(charge_start),
        "ChargeSubcategory": charge_subcategory,
        "CommitmentDiscountCategory": commitment_cat,
        "CommitmentDiscountId":       commitment_id,
        "CommitmentDiscountName":     commitment_name,
        "CommitmentDiscountType":     commitment_type,
        "EffectiveCost":     f"{effective_cost:.6f}",
        "InvoiceIssuer":     "Oracle Nederland B.V.",
        "ListCost":          f"{list_cost:.6f}",
        "ListUnitPrice":     f"{unit_price:.8f}",
        "PricingCategory":   pricing_category,
        "PricingQuantity":   f"{quantity:.8f}",
        "PricingUnit":       pricing_unit,
        "Provider":          "OCI",
        "Publisher":         "Oracle",
        "Region":            region,
        "ResourceId":        resource_id,
        "ResourceName":      resource_name,
        "ResourceType":      res_type,
        "ServiceCategory":   svc_cat,
        "ServiceName":       svc_name,
        "SkuId":             f"B{rnd.randint(80000, 99999)}",
        "SkuPriceId":        f"SKP-{rnd.randint(10000, 99999)}",
        "SubAccountId":      compartment_id,
        "SubAccountName":    compartment_name,
        "Tags":              tags,
        "UsageQuantity":     f"{quantity:.8f}",
        "UsageUnit":         usage_unit,
        "oci_ReferenceNumber":       ref_no,
        "oci_CompartmentId":         compartment_id,
        "oci_CompartmentName":       compartment_name,
        "oci_OverageFlag":           overage_flag,
        "oci_UnitPriceOverage":      unit_price_overage,
        "oci_BilledQuantityOverage": billed_qty_overage,
        "oci_CostOverage":           cost_overage,
        "oci_AttributedUsage":       "",
        "oci_AttributedCost":        "",
        "oci_BackReferenceNumber":   "",
    })


def main() -> int:
    p = argparse.ArgumentParser(description="Genereer synthetic FOCUS-CSV voor UC-12.")
    p.add_argument("--months", type=int, default=3,
                   help="Aantal maanden te genereren (default 3, eindigend vorige maand).")
    p.add_argument("--end-year", type=int, default=None,
                   help="Jaar van laatste maand (default: huidige jaar).")
    p.add_argument("--end-month", type=int, default=None,
                   help="Laatste maand (1-12; default: vorige maand t.o.v. vandaag).")
    p.add_argument("--seed", type=int, default=42, help="Random-seed voor reproducerbaarheid.")
    p.add_argument("--output", "-o", default="-",
                   help="Output-bestand (default stdout).")
    args = p.parse_args()

    today = datetime.now(timezone.utc)
    end_year = args.end_year if args.end_year is not None else today.year
    if args.end_month is not None:
        end_month = args.end_month
    else:
        end_month = today.month - 1 or 12
        if today.month == 1:
            end_year -= 1

    rnd = random.Random(args.seed)
    fp = sys.stdout if args.output == "-" else open(args.output, "w", encoding="utf-8", newline="")
    try:
        writer = csv.DictWriter(fp, fieldnames=FOCUS_COLUMNS)
        writer.writeheader()

        months = []
        y, m = end_year, end_month
        for _ in range(args.months):
            months.append((y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        months.reverse()

        for year, month in months:
            month_start, month_end = month_window(year, month)
            for compartment in COMPARTMENTS:
                env = "prod" if "prod" in compartment[1] else ("acc" if "acc" in compartment[1] else "test")
                for service in SERVICES:
                    for region_pair in REGIONS:
                        # Niet elke service draait in elke regio voor non-prod —
                        # houdt rij-aantal natuurlijk.
                        if env != "prod" and rnd.random() < 0.4:
                            continue
                        n_resources = rnd.randint(1, 3)
                        for seq in range(n_resources):
                            app = rnd.choice(APPLICATIONS)
                            cc = rnd.choice(COST_CENTERS)
                            emit_row(
                                writer, rnd,
                                month_start=month_start, month_end=month_end,
                                service=service, region_pair=region_pair,
                                compartment=compartment, environment=env,
                                application=app, cost_center=cc,
                                resource_seq=seq + 1,
                            )
    finally:
        if fp is not sys.stdout:
            fp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
