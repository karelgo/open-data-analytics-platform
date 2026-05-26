package trino

# Rol-gebaseerde resource-access.
#
# Bron-of-truth: data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.roles (uit data.json).
# Voor elke rol in user_roles:
#   1. Zit de target-catalog in roles[r].catalogs?
#   2. Zo ja, en is roles[r].schemas != null, zit de schema in die lijst?
#
# Een rol krijgt access als (a) catalog matcht én (b) schemas leeg is óf het
# schema in de toegestane set zit.

import rego.v1

# Wordt door trino-base.rego gebruikt als helper. Twee paden:
#   1. role.schemas == null      → catalog-membership is voldoende
#   2. role.schemas is een lijst → catalog ÉN schema moeten matchen
role_allows_resource if {
	some r in user_roles
	role := data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.roles[r]
	resource_catalog in role.catalogs
	role.schemas == null
}

role_allows_resource if {
	some r in user_roles
	role := data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.roles[r]
	resource_catalog in role.catalogs
	role.schemas != null
	resource_schema in role.schemas
}

# Helpers — extract catalog/schema/table uit input. Veiligheidsval:
# fallback op leeg als de operation geen resource heeft.

resource_catalog := c if {
	c := input.action.resource.table.catalogName
}

resource_catalog := c if {
	not input.action.resource.table
	c := input.action.resource.schema.catalogName
}

# ShowSchemas / catalog-level operations gebruiken `resource.catalog.name`.
resource_catalog := c if {
	not input.action.resource.table
	not input.action.resource.schema
	c := input.action.resource.catalog.name
}

resource_catalog := "" if {
	not input.action.resource.table
	not input.action.resource.schema
	not input.action.resource.catalog
}

resource_schema := s if {
	s := input.action.resource.table.schemaName
}

resource_schema := s if {
	not input.action.resource.table
	s := input.action.resource.schema.schemaName
}

resource_schema := "" if {
	not input.action.resource.table
	not input.action.resource.schema
}

# Capability-helpers — gebruikt door column-masks.
role_has_capability(role_name, cap) if {
	role := data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.roles[role_name]
	role[cap] == true
}

# True als ANY van de user_roles een capability heeft.
any_role_has_capability(cap) if {
	some r in user_roles
	role_has_capability(r, cap)
}
