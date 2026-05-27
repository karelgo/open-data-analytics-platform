package trino

import rego.v1

# DoD-check: OPA weigert query op `gold.uc05_customer_360.*` voor rol zonder
# matchende doelcode.
test_uc05_denied_without_purpose if {
	not allow with input as {
		"context": {"identity": {
			"user": "data.steward",
			"groups": ["data_steward"],
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc05_customer_360",
				"tableName": "mart_uc05_customer_360",
			}},
		},
	}
}

test_uc05_allowed_with_customer interaction_purpose if {
	allow with input as {
		"context": {"identity": {
			"user": "marketing.analyst",
			"groups": ["marketing_analyst"],
			"extraCredentials": {"purpose": "customer interaction"},
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc05_customer_360",
				"tableName": "mart_uc05_customer_360",
			}},
		},
	}
}

test_uc05_denied_with_wrong_purpose if {
	# marketing_analyst heeft `customer interaction` maar declareert `actuarie` → mismatch
	not allow with input as {
		"context": {"identity": {
			"user": "marketing.analyst",
			"groups": ["marketing_analyst"],
			"extraCredentials": {"purpose": "actuarie"},
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc05_customer_360",
				"tableName": "mart_uc05_customer_360",
			}},
		},
	}
}

test_uc01_allowed_with_sturingsinfo_purpose if {
	allow with input as {
		"context": {"identity": {
			"user": "data.steward",
			"groups": ["data_steward"],
			"extraCredentials": {"purpose": "sturingsinfo"},
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc01_claims_funnel",
				"tableName": "mart_uc01_claims_funnel_daily",
			}},
		},
	}
}

test_platform_admin_wildcard_purpose if {
	# platform_admin heeft `*` purpose; mag alles.
	allow with input as {
		"context": {"identity": {
			"user": "platform.admin",
			"groups": ["platform_admin"],
			"extraCredentials": {"purpose": "actuarie"},
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc05_customer_360",
				"tableName": "mart_uc05_customer_360",
			}},
		},
	}
}
