package trino

import rego.v1

# Claims Analyst in regio AMS → filter `regio_code = 'AMS'`.
test_claims_analyst_regio_filter if {
	filters := rowFilters with input as {
		"context": {"identity": {
			"user": "claims.analyst",
			"groups": ["claims_analyst"],
			"extraCredentials": {"regio": "ams"},
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "silver",
				"schemaName": "claims",
				"tableName": "aanvraag",
			}},
		},
	}
	count(filters) == 1
	filters[0].expression == "regio_code = 'AMS'"
}

# Andere rol op silver.wia → geen regio-filter.
test_no_regio_filter_for_data_steward if {
	rowFilters == [] with input as {
		"context": {"identity": {
			"user": "data.steward",
			"groups": ["data_steward"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "silver",
				"schemaName": "claims",
				"tableName": "aanvraag",
			}},
		},
	}
}

# UC-04 opt-out filter altijd actief.
test_uc04_opt_out_filter if {
	filters := rowFilters with input as {
		"context": {"identity": {
			"user": "outreach.specialist",
			"groups": ["marketing_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc04_eligibility_outreach",
				"tableName": "mart_uc04_eligibility_outreach",
			}},
		},
	}
	count(filters) == 1
	filters[0].expression == "opt_out = false"
}

# Regex-validatie: ongeldige regio (te lang) → geen filter (defensief).
test_invalid_regio_no_filter if {
	rowFilters == [] with input as {
		"context": {"identity": {
			"user": "claims.analyst",
			"groups": ["claims_analyst"],
			"extraCredentials": {"regio": "DROPTABLE"},
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "silver",
				"schemaName": "claims",
				"tableName": "aanvraag",
			}},
		},
	}
}

# UC-11 — claims_analyst in regio AMS op gold.uc11_customer_journey → regio-filter
# met fallback "OR regio_code IS NULL" zodat non-WIA events zichtbaar blijven.
test_uc11_claims_analyst_regio_filter if {
	filters := rowFilters with input as {
		"context": {"identity": {
			"user": "claims.analyst",
			"groups": ["claims_analyst"],
			"extraCredentials": {"regio": "ams"},
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc11_customer_journey",
				"tableName": "mart_uc11_journey_events",
			}},
		},
	}
	count(filters) == 1
	filters[0].expression == "regio_code = 'AMS' OR regio_code IS NULL"
}

# UC-11 — fraud_analyst mag medische uitkomst-events niet zien.
test_uc11_fraud_analyst_medical_filter if {
	filters := rowFilters with input as {
		"context": {"identity": {
			"user": "fraud.analyst",
			"groups": ["fraud_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc11_customer_journey",
				"tableName": "mart_uc11_journey_events",
			}},
		},
	}
	count(filters) == 1
	filters[0].expression == "NOT (domein = 'claims' AND event_status IN ('TOEGEKEND_WGA', 'TOEGEKEND_IVA'))"
}
