package trino

# Defence in depth if a contact field is accidentally exposed by a new model.
# Contacts are not part of the analytics contract; raw S3 objects require a
# separate storage credential and are never served by the public portal.
import rego.v1

columnMask := {"expression": "NULL"} if {
	lower(input.action.resource.column.columnName) in {"email", "phone", "raw_payload"}
	not any_role_has_capability("can_see_pii")
}
