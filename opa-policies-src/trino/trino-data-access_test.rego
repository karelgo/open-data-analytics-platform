package trino

import rego.v1

# Self-service data-access grants — DoD-checks bij ADR-0008.
#
# Scenario's:
#   1. researcher zonder grant op gold.uc05 → deny (primair rol-pad zegt
#      sandbox-only)
#   2. researcher MET grant + correcte purpose → allow
#   3. researcher MET grant maar VERKEERDE purpose → deny (doelbinding
#      blijft afgedwongen)
#   4. researcher MET grant maar lege catalog (e.g. metadata-query) →
#      geen synthetic bypass

test_researcher_without_grant_denied if {
	not allow with input as {
		"context": {"identity": {
			"user": "alice.researcher",
			"groups": ["researcher"],
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

test_researcher_with_grant_and_purpose_allowed if {
	allow with input as {
		"context": {"identity": {
			"user": "alice.researcher",
			"groups": ["researcher", "data_access:gold.uc05_client_360"],
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

# Doelbinding blijft afgedwongen onder een grant: een verkeerde purpose op
# een resource met purpose-eis wordt geweigerd. Mockt data.configmap zodat
# doelbinding-keten daadwerkelijk vuurt (anders valt resource_required_
# purposes terug op []).
test_grant_does_not_bypass_doelbinding if {
	not purpose_allows_resource with input as {
		"context": {"identity": {
			"user": "alice.researcher",
			"groups": ["researcher", "data_access:gold.uc05_client_360"],
			"extraCredentials": {"purpose": "handhaving"},
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
		with data.configmap as {"opa-trino-bundle": {"odap-platform": {"role_mappings": {
			"resource_purposes": {"gold.uc05_client_360.*": ["klantcontact", "behandeling"]},
			"roles": {"researcher": {
				"purposes": ["statistisch_onderzoek"],
				"catalogs": ["sandbox"],
				"schemas": null,
			}},
		}}}}
}

# Spiegel: zelfde grant + GOEDE purpose → purpose_allows_resource = true.
test_grant_with_matching_purpose_permits_doelbinding if {
	purpose_allows_resource with input as {
		"context": {"identity": {
			"user": "alice.researcher",
			"groups": ["researcher", "data_access:gold.uc05_client_360"],
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
		with data.configmap as {"opa-trino-bundle": {"odap-platform": {"role_mappings": {
			"resource_purposes": {"gold.uc05_client_360.*": ["klantcontact", "behandeling"]},
			"roles": {"researcher": {
				"purposes": ["statistisch_onderzoek"],
				"catalogs": ["sandbox"],
				"schemas": null,
			}},
		}}}}
}

# Negatieve sanity-check: lege catalog/schema mag GEEN universele grant
# triggeren via `data_access:.`.
test_empty_resource_does_not_bypass if {
	not role_allows_resource with input as {
		"context": {"identity": {
			"user": "alice.researcher",
			"groups": ["researcher", "data_access:."],
		}},
		"action": {
			"operation": "ExecuteQuery",
		},
	}
}

test_grant_on_other_schema_does_not_apply if {
	# Grant op uc04, query op uc05 → mismatch, geen allow.
	not allow with input as {
		"context": {"identity": {
			"user": "alice.researcher",
			"groups": ["researcher", "data_access:gold.uc04_tw_eligibility"],
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
