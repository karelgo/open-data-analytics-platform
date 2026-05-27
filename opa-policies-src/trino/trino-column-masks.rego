package trino

# Column masks (R-AVG-07 + R-BIO-11).
#
# Per (rol × kolom) een SQL-mask die Trino in de SELECT-projection toepast.
# Trino verwacht: data.trino.columnMask → { "expression": "..." }
#
# Default: geen mask (cleartext).
#
# Mask-categorieën:
#   - BSN:          show last 4 (`'XXXXX' || substr(bsn, 6, 4)`)  voor marketing_analyst
#   - IBAN/bankrekening:  fully masked  (`'NLxx XXXX XXXX XXXX'`) voor wie geen `can_see_bankrekening`
#   - diagnose/icd10: NULL  voor wie geen `can_see_medical`
#   - birth_date: bucket-per-jaar  (`date_trunc('year', birth_date)`) voor data_steward
#   - default voor andere PII bij rollen zonder `can_see_pii`: NULL

import rego.v1

# --- BSN: maskeer voor marketing_analyst ---------------------------------
columnMask := {"expression": expr} if {
	column_lower == "bsn"
	"marketing_analyst" in user_roles
	expr := "concat('XXXXX', substr(bsn, 6, 4))"
}

# --- BSN: hard-mask voor rollen zonder can_see_pii --------------------
columnMask := {"expression": "concat('XXXXXX', substr(bsn, 7, 3))"} if {
	column_lower == "bsn"
	not "marketing_analyst" in user_roles # die heeft eigen mask
	not any_role_has_capability("can_see_pii")
}

# --- IBAN / bankrekening: deny voor wie niet can_see_bankrekening -----
columnMask := {"expression": "'NLxx XXXX XXXX XXXX'"} if {
	column_lower in {"iban", "bankrekening"}
	not any_role_has_capability("can_see_bankrekening")
	not any_role_has_capability("break_glass")
}

# --- diagnose / icd10: NULL voor wie niet can_see_medical -------------
columnMask := {"expression": "NULL"} if {
	column_lower in {"diagnose", "icd10"}
	not any_role_has_capability("can_see_medical")
	not any_role_has_capability("break_glass")
}

# --- birth_date: bucket-per-jaar voor data_steward -----------------
columnMask := {"expression": "date_trunc('year', birth_date)"} if {
	column_lower == "birth_date"
	"data_steward" in user_roles
	count(user_roles) == 1 # alleen als data_steward de enige rol is
}

# --- UC-11 — event_label sanitization voor non-medische rollen --------
# Klantreis-labels kunnen medische info bevatten (bv. "WIA-aanvraag, AO 80%").
# Voor marketing_analyst / fraud_analyst / data_steward redigeren we het label tot
# een generiek "WIA-procedure"-label.
columnMask := {"expression": "concat(domein, '.', event_type)"} if {
	column_lower == "event_label"
	resource_schema_lower == "uc11_customer_journey"
	not any_role_has_capability("can_see_medical")
	not any_role_has_capability("break_glass")
}

# UC-11 — source_ref_id (orig. primary key) gemaskeerd voor non-supervisor.
columnMask := {"expression": "'***'"} if {
	column_lower == "source_ref_id"
	resource_schema_lower == "uc11_customer_journey"
	not any_role_has_capability("can_see_pii")
	not "marketing_analyst" in user_roles
}

# --- helpers ----------------------------------------------------------
column_lower := lower(input.action.resource.column.columnName)

resource_schema_lower := lower(input.action.resource.column.schemaName)
