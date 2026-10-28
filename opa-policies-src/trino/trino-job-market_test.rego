package trino

import rego.v1

job_input(roles, purpose, op, catalog, schema) := {
	"context": {"identity": {
		"user": "analyst", "groups": roles,
		"extraCredentials": {"purpose": purpose},
	}},
	"action": {"operation": op, "resource": {"table": {"catalogName": catalog, "schemaName": schema, "tableName": object.get({"gold": "mart_job_inventory", "silver": "stg_job_observations"}, catalog, "observations")}}},
}

test_analyst_reads_gold_with_research_purpose if {
	allow with input as job_input(["claims_analyst"], "labour_market_research", "SelectFromColumns", "gold", "job_market")
}

test_analyst_cannot_read_bronze if {
	not allow with input as job_input(["claims_analyst"], "labour_market_research", "SelectFromColumns", "bronze", "job_market")
}

test_wrong_purpose_denied if {
	not allow with input as job_input(["claims_analyst"], "candidate_screening", "SelectFromColumns", "gold", "job_market")
}

test_missing_purpose_denied if {
	not allow with input as job_input(["claims_analyst"], "", "SelectFromColumns", "gold", "job_market")
}

test_researcher_reads_sanitized_silver if {
	allow with input as job_input(["researcher"], "labour_market_research", "SelectFromColumns", "silver", "job_market")
}

test_steward_reads_bronze_for_quality if {
	allow with input as job_input(["data_steward"], "quality_control", "SelectFromColumns", "bronze", "job_market")
}

test_analyst_cannot_write if {
	not allow with input as job_input(["claims_analyst"], "labour_market_research", "CreateTable", "gold", "job_market")
}

test_engineer_builds_gold if {
	allow with input as job_input(["data_engineer"], "labour_market_research", "CreateTable", "gold", "job_market")
}

test_retired_schema_denied if {
	not allow with input as job_input(["claims_analyst"], "labour_market_research", "SelectFromColumns", "gold", "retired_example")
}

test_unknown_role_denied if {
	not allow with input as job_input(["unknown"], "labour_market_research", "SelectFromColumns", "gold", "job_market")
}

test_anonymous_denied if {
	not allow with input as {"context": {"identity": {"user": "", "groups": []}}, "action": {"operation": "ExecuteQuery"}}
}

test_existing_self_service_grant_still_works if {
	allow with input as job_input(["data_access:silver.job_market"], "labour_market_research", "SelectFromColumns", "silver", "job_market")
}

test_contact_column_masked if {
	columnMask == {"expression": "NULL"} with input as {
		"context": {"identity": {"user": "analyst", "groups": ["claims_analyst"]}},
		"action": {"resource": {"column": {"columnName": "email"}}},
	}
}

test_gold_alias_cannot_read_bronze_observations if {
	request := job_input(["claims_analyst"], "labour_market_research", "SelectFromColumns", "gold", "job_market")
	spoofed := object.union(request, {"action": {"operation": "SelectFromColumns", "resource": {"table": {"catalogName": "gold", "schemaName": "job_market", "tableName": "observations"}}}})
	not allow with input as spoofed
}

test_self_service_grant_does_not_bypass_layer_boundary if {
	not allow with input as {
		"context": {"identity": {
			"user": "researcher", "groups": ["data_access:gold.job_market"],
			"extraCredentials": {"purpose": "labour_market_research"},
		}},
		"action": {"operation": "SelectFromColumns", "resource": {"table": {"catalogName": "gold", "schemaName": "job_market", "tableName": "stg_job_observations"}}},
	}
}
