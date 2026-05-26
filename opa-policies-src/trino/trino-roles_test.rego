package trino

import rego.v1

# Tests voor role-resource-access (catalog + schema-membership).

test_data_steward_allowed_in_silver if {
	role_allows_resource with input as {
		"context": {"identity": {"user": "data.steward", "groups": ["data_steward"]}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "silver",
				"schemaName": "polisadm",
				"tableName": "ikv",
			}},
		},
	}
}

test_crm_medewerker_denied_outside_uc05 if {
	# crm_medewerker mag alleen `gold.uc05_client_360.*` zien.
	not role_allows_resource with input as {
		"context": {"identity": {"user": "crm.medewerker", "groups": ["crm_medewerker"]}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "silver",
				"schemaName": "wia",
				"tableName": "aanvraag",
			}},
		},
	}
}

test_wia_beoordelaar_only_wia_schemas if {
	role_allows_resource with input as {
		"context": {"identity": {"user": "wia.beoordelaar", "groups": ["wia_beoordelaar"]}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "silver",
				"schemaName": "wia",
				"tableName": "aanvraag",
			}},
		},
	}
}

test_wia_beoordelaar_denied_in_polisadm if {
	# polisadm zit niet in wia_beoordelaar.schemas
	not role_allows_resource with input as {
		"context": {"identity": {"user": "wia.beoordelaar", "groups": ["wia_beoordelaar"]}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "silver",
				"schemaName": "polisadm",
				"tableName": "ikv",
			}},
		},
	}
}

test_platform_admin_full_catalog_access if {
	role_allows_resource with input as {
		"context": {"identity": {"user": "platform.admin", "groups": ["platform_admin"]}},
		"action": {
			"operation": "SelectFromColumns",
			"resource": {"table": {
				"catalogName": "sensitive",
				"schemaName": "wajong",
				"tableName": "dossier",
			}},
		},
	}
}
