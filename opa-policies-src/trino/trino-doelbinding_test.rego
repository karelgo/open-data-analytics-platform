package trino

import rego.v1

# DoD-check: OPA weigert query op `gold.uc05_client_360.*` voor rol zonder
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
				"schemaName": "uc05_client_360",
				"tableName": "mart_uc05_client_360",
			}},
		},
	}
}

test_uc05_allowed_with_klantcontact_purpose if {
	allow with input as {
		"context": {"identity": {
			"user": "marketing.analyst",
			"groups": ["marketing_analyst"],
			"extraCredentials": {"purpose": "klantcontact"},
		}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "gold",
				"schemaName": "uc05_client_360",
				"tableName": "mart_uc05_client_360",
			}},
		},
	}
}

test_uc05_denied_with_wrong_purpose if {
	# marketing_analyst heeft `klantcontact` maar declareert `actuarie` → mismatch
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
				"schemaName": "uc05_client_360",
				"tableName": "mart_uc05_client_360",
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
				"schemaName": "uc01_wia_funnel",
				"tableName": "mart_uc01_wia_funnel_daily",
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
				"schemaName": "uc05_client_360",
				"tableName": "mart_uc05_client_360",
			}},
		},
	}
}
