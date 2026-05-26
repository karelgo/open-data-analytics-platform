package trino

# Doelbinding (R-AVG-05 + R-AVG-06).
#
# Per resource: welke purposes zijn toegestaan?
# Per rol:      welke purposes mag de rol declareren?
#
# Allow-rule: er is overlap tussen
#   resource_required_purposes  (uit data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.resource_purposes)
#   user_purpose                (uit input.context.identity.extraCredentials.purpose)
#   role_allowed_purposes       (uit data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.roles[r].purposes)

import rego.v1

# --- helpers -----------------------------------------------------------

# Wildcard-match `gold.uc05_client_360.*` matched een tabel `mart_uc05_client_360`.
# We bouwen een sleutel `<catalog>.<schema>.*` en `<catalog>.<schema>.<table>`,
# en pakken de eerste matchende waarde.
resource_required_purposes := purposes if {
	# Exact match op tabel-niveau krijgt voorrang.
	key := concat(".", [resource_catalog, resource_schema, resource_table])
	purposes := data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.resource_purposes[key]
}

resource_required_purposes := purposes if {
	# Wildcard match op schema-niveau.
	key := concat(".", [resource_catalog, resource_schema, "*"])
	purposes := data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.resource_purposes[key]

	# Voorkom dubbele resolution: alleen als geen exact match.
	exact_key := concat(".", [resource_catalog, resource_schema, resource_table])
	not data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.resource_purposes[exact_key]
}

# Default — geen restrictie als resource niet in mapping.
resource_required_purposes := [] if {
	not _has_purpose_mapping
}

_has_purpose_mapping if {
	exact := concat(".", [resource_catalog, resource_schema, resource_table])
	data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.resource_purposes[exact]
}

_has_purpose_mapping if {
	wild := concat(".", [resource_catalog, resource_schema, "*"])
	data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.resource_purposes[wild]
}

# Helper voor table-naam.
resource_table := t if {
	t := input.action.resource.table.tableName
} else := ""

# Welke purposes mag deze user declareren? Som per rol.
user_allowed_purposes contains p if {
	some r in user_roles
	role := data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.roles[r]
	some p in role.purposes
}

# Wildcard-purpose (`*`) — platform_admin mag alles.
user_has_wildcard_purpose if {
	"*" in user_allowed_purposes
}

# --- main rule ---------------------------------------------------------

# Resource heeft geen restrictie → allow.
purpose_allows_resource if {
	count(resource_required_purposes) == 0
}

# Wildcard-rol: bypass.
purpose_allows_resource if {
	user_has_wildcard_purpose
}

# Match: user-purpose (header) zit in resource-required-purposes
# EN user-rol mag die purpose declareren.
purpose_allows_resource if {
	user_purpose in resource_required_purposes
	user_purpose in user_allowed_purposes
}
