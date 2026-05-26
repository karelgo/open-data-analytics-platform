package trino

import rego.v1

# DoD-check: OPA maskeert BSN voor marketing_analyst.
test_bsn_masked_for_marketing_analyst if {
	mask := columnMask with input as {
		"context": {"identity": {
			"user": "marketing.analyst",
			"groups": ["marketing_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"column": {
				"catalogName": "gold",
				"schemaName": "uc05_client_360",
				"tableName": "mart_uc05_client_360",
				"columnName": "bsn",
			}},
		},
	}
	mask.expression == "concat('XXXXX', substr(bsn, 6, 4))"
}

# Wia_beoordelaar mag PII zien — geen mask op BSN.
test_bsn_unmasked_for_claims_analyst if {
	columnMask == {} with input as {
		"context": {"identity": {
			"user": "claims.analyst",
			"groups": ["claims_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"column": {
				"catalogName": "silver",
				"schemaName": "wia",
				"tableName": "stg_wia_aanvraag",
				"columnName": "bsn",
			}},
		},
	}
}

# Diagnose: NULL voor marketing_analyst (geen can_see_medical).
test_diagnose_nulled_for_marketing_analyst if {
	mask := columnMask with input as {
		"context": {"identity": {
			"user": "marketing.analyst",
			"groups": ["marketing_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"column": {
				"catalogName": "sensitive",
				"schemaName": "wajong",
				"tableName": "dossier",
				"columnName": "diagnose",
			}},
		},
	}
	mask.expression == "NULL"
}

# Diagnose: cleartext voor claims_analyst.
test_diagnose_visible_for_claims_analyst if {
	columnMask == {} with input as {
		"context": {"identity": {
			"user": "case.manager",
			"groups": ["claims_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"column": {
				"catalogName": "sensitive",
				"schemaName": "wajong",
				"tableName": "dossier",
				"columnName": "diagnose",
			}},
		},
	}
}

# IBAN: gemaskeerd voor marketing_analyst (geen can_see_bankrekening).
test_iban_masked_for_marketing_analyst if {
	mask := columnMask with input as {
		"context": {"identity": {
			"user": "marketing.analyst",
			"groups": ["marketing_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"column": {
				"catalogName": "gold",
				"schemaName": "uc05_client_360",
				"tableName": "mart_uc05_client_360",
				"columnName": "iban",
			}},
		},
	}
	mask.expression == "'NLxx XXXX XXXX XXXX'"
}

# IBAN: cleartext voor fraud_analyst (heeft can_see_bankrekening).
test_iban_visible_for_fraud_analyst if {
	columnMask == {} with input as {
		"context": {"identity": {
			"user": "fraud.analyst",
			"groups": ["fraud_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"column": {
				"catalogName": "silver",
				"schemaName": "ww",
				"tableName": "aanvraag",
				"columnName": "iban",
			}},
		},
	}
}

# UC-11 — event_label gesanitized voor marketing_analyst (geen can_see_medical).
test_uc11_event_label_sanitized_for_marketing_analyst if {
	mask := columnMask with input as {
		"context": {"identity": {
			"user": "marketing.analyst",
			"groups": ["marketing_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"column": {
				"catalogName": "gold",
				"schemaName": "uc11_klantreis",
				"tableName": "mart_uc11_klantreis_events",
				"columnName": "event_label",
			}},
		},
	}
	mask.expression == "concat(domein, '.', event_type)"
}

# UC-11 — event_label cleartext voor claims_analyst (heeft can_see_medical).
test_uc11_event_label_visible_for_claims_analyst if {
	columnMask == {} with input as {
		"context": {"identity": {
			"user": "claims.analyst",
			"groups": ["claims_analyst"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"column": {
				"catalogName": "gold",
				"schemaName": "uc11_klantreis",
				"tableName": "mart_uc11_klantreis_events",
				"columnName": "event_label",
			}},
		},
	}
}
