package trino

# Self-service data-access grants (ADR-0008).
#
# Een gebruiker met realm-role `data_access:<catalog>.<schema>` krijgt
# toegang op die catalog + schema, ongeacht zijn primaire rol-mapping.
# Het webhook-pad (`om-access-bridge`) is de enige bron van deze rollen —
# zie ADR-0008 voor de approval-flow.
#
# Twee uitbreidingen op de basis-policies:
#   1. role_allows_resource: een grant-rol matched de target catalog/schema
#   2. user_allowed_purposes: de aanvrager mag élke purpose declareren die
#      op de granted resource staat (resource_required_purposes bepaalt
#      de toegestane purposes — zie trino-doelbinding.rego)

import rego.v1

# --- helpers -----------------------------------------------------------

# Naamsconventie afgedwongen door om-access-bridge.
grant_role_for_resource := concat("", [
	"data_access:",
	resource_catalog,
	".",
	resource_schema,
])

# Heeft de user een grant-rol die de huidige resource dekt?
has_data_access_grant if {
	grant_role_for_resource in user_roles
}

# --- uitbreiding van role_allows_resource ------------------------------

# Naast de bestaande paden in trino-platform-roles.rego: een grant-rol is
# eveneens voldoende. Resource-catalog/schema moeten niet leeg zijn —
# anders zou `data_access:.` als universele bypass werken.
role_allows_resource if {
	resource_catalog != ""
	resource_schema != ""
	has_data_access_grant
}

# --- uitbreiding van user_allowed_purposes -----------------------------

# Iedere purpose die op de granted resource staat is toegestaan voor de
# user. Geen aparte purpose-rollen nodig.
user_allowed_purposes contains p if {
	has_data_access_grant
	some p in resource_required_purposes
}
