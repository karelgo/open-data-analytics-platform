# UC-07 — Datakwaliteit polisadministratie

| Status in deze repo | **Volledig geïmplementeerd** als dbt-tests + OM-profiler |
|---|---|
| Domein | Polisadministratie (cross-domein fundament) |
| Risicoclassificatie | Laag (interne kwaliteitscontrole) |
| AVG-grondslag | Art. 6 lid 1c (wettelijke verplichting) + 1e |
| Juistheidsprincipe | Art. 5 lid 1d AVG — actief invulling |

Bron: [`referentiearchitectuur-odap-data-analytics.md` § 8 UC-07](../../referentiearchitectuur-odap-data-analytics.md).

---

## Probleem

Polisadministratie (~21,2 mln IKV's, ~13,8 mln personen) is fundament voor
dagloon, WW, WIA en gegevensleveringen. Fouten in IKV's leiden tot fouten in
uitkeringen.

## Doel

Continue datakwaliteits-monitoring met automatische detectie van afwijkingen
en correctievoorstellen voor data-stewards.

## Data

| Bron | Inhoud |
|---|---|
| Aangifte loonheffingen (Belastingdienst) | Periodieke aangiftes |
| Polisadministratie | IKV's, dienstverbanden |
| BRP-spiegel | Persoonsgegevens (referentie) |
| Eerdere correcties | Audit-trail |
| Pensioenfonds-data | Cross-reference (uit fictieve bron) |

**CGM-entiteiten**: `IKV`, `Werknemer`, `Werkgever`.

## Architectuur-pad

```
NiFi: ingest aangiftes  → ValidateRecord (schema-validatie) →
   ├── valide      → Kafka uwv.polisadm.aangifte
   └── invalide    → Kafka uwv.polisadm.aangifte_quarantine + alert
            │
            ▼
Spark Streaming   → bronze.polisadm.aangifte (Delta)
            │
            ▼
dbt staging: stg_polisadm_aangifte, stg_polisadm_ikv  → silver.polisadm.*
            │
            ▼
dbt mart: mart_uc07_dq_polisadm  → gold.uc07_dq_polisadm.dq_dagrapport
            │
            ▼
Superset dashboard "Polisadm DQ" voor data-steward + Airflow alert-DAG
```

## dbt-tests (kritiek voor deze UC)

Generieke tests:

- `unique(aangifte_id)`
- `not_null(bsn, lh_nummer, periode)`
- `accepted_values(aangifte_status, ['INGEDIEND','ACCEPTED','GECORRIGEERD','AFGEKEURD'])`
- `relationships(bsn → silver.brp_spiegel.bsn)`

Custom tests (singular):

- `test_bsn_checksum.sql` — 11-proef voor elke BSN.
- `test_iban_format.sql` — IBAN-controle (mod-97).
- `test_lh_nummer_format.sql` — Loonheffingennummer-format.
- `test_loon_consistency.sql` — som per IKV gelijk aan jaarbedrag in BRP-koppeling.
- `dbt-expectations`: `expect_column_value_lengths_to_equal(bsn, 9)`,
  `expect_column_values_to_match_regex(iban, '^NL[0-9]{2}[A-Z]{4}[0-9]{10}$')`.

## OpenMetadata profiler

Op `silver.polisadm.ikv`:

- Volume-metric: aantal IKV's per dag, alert bij Δ > 5%.
- Null-fractie per kolom, alert bij toename > 1%.
- Unique-count `bsn`, alert bij teruglopen.

## dbt-model `meta`

```yaml
meta:
  domain: polisadm
  legal_basis: Wet_SUWI+Wfsv
  doelbinding: [primair_proces, kwaliteitscontrole]
  bio_classificatie: vertrouwelijk
  bewaartermijn_jaren: 30   # polisadministratie wettelijk lang
  eigenaar: data_steward_polisadm
  pii_kolommen: [bsn, lh_nummer]
  risk_tier: laag
  juistheid_AVG_art_5_1d: true
```

## OPA-policies

- Toegang tot `gold.uc07_dq_polisadm.*` alleen voor `data_steward` met doelcode
  `kwaliteitscontrole`.
- Inzage in details (bsn-niveau): `data_steward_polisadm` + JIT-token.
- Aggregaten: alle data_stewards.

## Outputs

- `data-generation/generators/polisadministratie.py` met BSN-checksum-injecteur
  voor `test_bsn_checksum`-coverage.
- `dbt/models/staging/polisadm/{stg_polisadm_aangifte.sql, stg_polisadm_ikv.sql, schema.yml}`.
- `dbt/models/marts/uc07_dq_polisadm/{mart_uc07_dq_dagrapport.sql, schema.yml}`.
- `dbt/tests/{test_bsn_checksum.sql, test_iban_format.sql, test_lh_nummer_format.sql, test_loon_consistency.sql}`.
- `platform/13-openmetadata-config/profiler/polisadm-profile.yaml`.
- `platform/12-superset/dashboards/uc07-polisadm-dq.json`.

## DoD-koppeling

UC-07 is onderdeel van de DoD: "dbt-test `bsn_valid` faalt op een ingespoten
ongeldige BSN-record" (zie [Originele referentie § Definition of Done](../architectuur/referentie.md#definition-of-done)).
