package trino

# =====================================================================
#  ODAP PLATFORM — TRINO OPA BASE POLICY (fase 9)
# =====================================================================
#
#  Vervangt de allow-all base-policy uit fase 3.
#  Default-deny + bouwt allow op via:
#    - role-mapping     (trino-platform-roles.rego)
#    - purpose-limitation      (trino-purpose-limitation.rego, R-AVG-06)
#    - row filters      (trino-row-filters.rego, R-BIO-11)
#    - column masks     (trino-column-masks.rego, R-AVG-07 + R-BIO-11)
#
#  Trino OPA Access Controller spec (v2):
#    https://trino.io/docs/current/security/opa-access-control.html
# =====================================================================

import rego.v1

# --- defaults ----------------------------------------------------------

default allow := false

default rowFilters := []

default columnMask := {}

# Trino OPA-plugin (Trino 477+) verwacht batched column-masks als array.
# Zonder default-rule: 'Failed to deserialize OPA policy response'.
default batchColumnMasks := []

# --- helpers -----------------------------------------------------------

# Authenticated user is altijd verplicht.
authenticated if {
	input.context.identity.user
	input.context.identity.user != ""
}

# ODAP roles uit Keycloak: groups-claim of (fallback) leeg.
user_roles := groups if {
	groups := input.context.identity.groups
	count(groups) > 0
}

# Voor static-auth (smoketest user, geen groups) plak handmatig de rol op
# o.b.v. de username.
user_roles := ["smoketest"] if {
	input.context.identity.user == "smoketest"
	count(object.get(input.context.identity, "groups", [])) == 0
}

default user_roles := []

# Purpose komt via Trino's `extraCredentials` (HTTP-header X-Trino-Extra-Credential).
# Lege string = geen purpose meegegeven.
user_purpose := lower(input.context.identity.extraCredentials.purpose) if {
	input.context.identity.extraCredentials.purpose
}

user_purpose := "" if {
	not input.context.identity.extraCredentials
}

user_purpose := "" if {
	input.context.identity.extraCredentials
	not input.context.identity.extraCredentials.purpose
}

# Operation-categorisatie.
is_read_op if input.action.operation == "SelectFromColumns"

is_read_op if input.action.operation == "ReadFromTable"

is_read_op if input.action.operation == "FilterColumns"

is_read_op if input.action.operation == "ShowSchemas"

is_read_op if input.action.operation == "ShowTables"

is_read_op if input.action.operation == "ShowColumns"

# FilterCatalogs/FilterSchemas/FilterTables — bulk-checks die Trino doet
# voor SHOW-queries en JDBC-metadata. OPA-batch-rule gebruikt is_read_op.
is_read_op if input.action.operation == "FilterCatalogs"

is_read_op if input.action.operation == "FilterSchemas"

is_read_op if input.action.operation == "FilterTables"

is_read_op if input.action.operation == "FilterViews"

is_meta_op if input.action.operation == "ExecuteQuery"

is_meta_op if input.action.operation == "AccessCatalog"

is_meta_op if input.action.operation == "ImpersonateUser"

is_meta_op if input.action.operation == "ReadSystemInformation"

is_write_op if input.action.operation == "InsertIntoTable"

is_write_op if input.action.operation == "DeleteFromTable"

is_write_op if input.action.operation == "TruncateTable"

is_write_op if input.action.operation == "DropTable"

is_write_op if input.action.operation == "DropSchema"

is_write_op if input.action.operation == "CreateTable"

is_write_op if input.action.operation == "CreateSchema"

is_write_op if input.action.operation == "CreateView"

is_write_op if input.action.operation == "CreateViewWithSelectFromColumns"

is_write_op if input.action.operation == "DropView"

is_write_op if input.action.operation == "RenameTable"

is_write_op if input.action.operation == "RenameSchema"

is_write_op if input.action.operation == "RenameView"

is_write_op if input.action.operation == "SetSchemaAuthorization"

is_write_op if input.action.operation == "SetTableProperties"

is_write_op if input.action.operation == "AddColumn"

is_write_op if input.action.operation == "DropColumn"

is_write_op if input.action.operation == "RenameColumn"

# Connector-procedures (CALL <catalog>.system.<proc>(...)). Trino stuurt
# `ExecuteProcedure` voor o.a. delta_lake's `system.register_table` —
# nodig om Python-side geschreven Delta-tabellen in HMS te registreren.
# Behandelen we als write: alleen technische schrijvers mogen het.
is_write_op if input.action.operation == "ExecuteProcedure"

# --- top-level allow ---------------------------------------------------

# Meta-operations (cataloglist, queryplan, etc.) — alleen authenticated.
allow if {
	authenticated
	is_meta_op
}

# Read-operations — full chain: role + purpose-limitation.
allow if {
	authenticated
	is_read_op
	layer_allows_resource
	role_allows_resource
	purpose_allows_resource
}

# Write-operations — alleen voor data_engineer + platform_admin + smoketest.
# smoketest is technische dbt-runner, krijgt write op bronze/silver/gold.
allow if {
	authenticated
	is_write_op
	role_allows_resource
	some r in user_roles
	r in {"data_engineer", "platform_admin", "smoketest"}
}

# --- batch (voor SHOW TABLES / FilterColumns op een lijst) ------------
batch contains i if {
	authenticated
	some i, _ in input.action.filterResources

	# Vrijgevig op meta-list-ops; per-resource policies vangen het later af.
	is_read_op
}

# All three Trino catalogs use the same Hive Metastore. A Gold catalog name
# alone does not prevent reading a Bronze Delta table through an alias.
# Enforce the logical layer by both catalog and table name, including grants.
layer_allows_resource if resource_schema != "job_market"

layer_allows_resource if resource_table == ""

layer_allows_resource if {
	resource_catalog == "bronze"
	resource_table == "observations"
}

layer_allows_resource if {
	resource_catalog == "silver"
	resource_table in {"stg_job_observations", "int_job_snapshots"}
}

layer_allows_resource if {
	resource_catalog == "gold"
	resource_table in {
		"mart_job_inventory", "mart_job_demand_daily", "mart_job_skills",
		"mart_job_salary", "mart_job_geography", "mart_job_work_arrangements",
		"mart_job_source_quality",
	}
}
