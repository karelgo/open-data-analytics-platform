package trino

# Row filters (R-BIO-11).
#
# Per (rol × schema) een filter-expressie die Trino aan elke SELECT toevoegt.
# Trino verwacht: data.trino.rowFilters → [ { "expression": "..." }, ... ]
#
# Implementaties:
#   - Claims Analyst in `silver.claims.*` of `gold.uc01_claims_funnel.*`:
#       regio_code = '<eigen regio uit extraCredentials.regio>'
#   - UC-04 mart: opt_out = false  (verberg cliënten die zich hebben afgemeld)

import rego.v1

# WIA-regio-filter
rowFilters := [{"expression": expr}] if {
	some r in user_roles
	r == "claims_analyst"
	resource_schema in {"claims", "uc01_claims_funnel"}
	regio := lower(input.context.identity.extraCredentials.regio)
	regio != ""

	# String-injection-safe: regio mag alleen [A-Z]{3} matchen.
	regex.match("^[a-z]{3}$", regio)
	expr := sprintf("regio_code = '%s'", [upper(regio)])
}

# UC-04 opt-out filter — verbergt opt-out cliënten for the werklijst.
rowFilters := [{"expression": "opt_out = false"}] if {
	resource_schema == "uc04_eligibility_outreach"
}

# Sandbox UC-09: alleen records met pseudo-IDs (defensief; in production
# is `sandbox.*` al exclusief gepseudonimiseerd).
rowFilters := [{"expression": "bsn_pseudo IS NOT NULL"}] if {
	resource_catalog == "sandbox"
}

# UC-11 — claims_analyst ziet customer journey-events alleen voor eigen regio.
# `regio_code` is alleen gevuld voor WIA-events; non-WIA events (regio_code IS NULL)
# blijven zichtbaar zodat de tijdlijn niet onnodig leeg is.
rowFilters := [{"expression": expr}] if {
	some r in user_roles
	r == "claims_analyst"
	resource_schema == "uc11_customer_journey"
	regio := lower(input.context.identity.extraCredentials.regio)
	regio != ""
	regex.match("^[a-z]{3}$", regio)
	expr := sprintf("regio_code = '%s' OR regio_code IS NULL", [upper(regio)])
}

# UC-11 — fraud_analyst mag geen medische WIA-status-events zien (IVA = duurzaam).
# Filter sluit medische uitkomst-events uit; aanvraag-meta blijft zichtbaar.
rowFilters := [{"expression": expr}] if {
	some r in user_roles
	r == "fraud_analyst"
	resource_schema == "uc11_customer_journey"
	expr := "NOT (domein = 'claims' AND event_status IN ('TOEGEKEND_WGA', 'TOEGEKEND_IVA'))"
}
