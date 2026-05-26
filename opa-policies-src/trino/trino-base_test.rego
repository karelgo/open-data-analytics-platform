package trino

import rego.v1

# Helper: bouw een minimaal input-record voor tests.
mock_input(user, roles, op, catalog, schema, table) := {
	"context": {"identity": {
		"user": user,
		"groups": roles,
	}},
	"action": {
		"operation": op,
		"resource": {"table": {
			"catalogName": catalog,
			"schemaName": schema,
			"tableName": table,
		}},
	},
}

mock_input_with_purpose(user, roles, purpose, op, catalog, schema, table) := r if {
	r := {
		"context": {"identity": {
			"user": user,
			"groups": roles,
			"extraCredentials": {"purpose": purpose},
		}},
		"action": {
			"operation": op,
			"resource": {"table": {
				"catalogName": catalog,
				"schemaName": schema,
				"tableName": table,
			}},
		},
	}
}

# --- baseline tests ----------------------------------------------------

test_anonymous_denied if {
	not allow with input as {
		"context": {"identity": {"user": "", "groups": []}},
		"action": {"operation": "ExecuteQuery"},
	}
}

test_authenticated_meta_query_allowed if {
	allow with input as {
		"context": {"identity": {"user": "data.steward", "groups": ["data_steward"]}},
		"action": {"operation": "ExecuteQuery"},
	}
}

test_user_with_no_role_denied if {
	not allow with input as mock_input(
		"alice", [], "SelectFromColumns",
		"gold", "uc01_wia_funnel", "mart_uc01_wia_funnel_daily",
	)
		with data.role_mappings as data.role_mappings
}
