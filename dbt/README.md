# dbt — Open Data & Analytics Platform

Transformatielaag van **bronze.demo.\*** (raw event-envelopes) naar
**silver.\<domein\>.\***  (CGM-conform getypt) en **gold.\<uc\>.\***
(business products).

## Layers

| Laag | Catalog | Materialized | Doel |
|---|---|---|---|
| `staging` | `silver` | view | Parsen van `bronze.demo.<entity>.payload` JSON naar typed kolommen |
| `intermediate` | `silver` | view | Joins, aggregaties die door meerdere marts hergebruikt worden |
| `marts` | `gold` | table | UC-specifieke business products (UC-01/04/05/06/07 in fase 5) |

Format-keuze (delta vs iceberg) komt via `var('table_format')` —
default `delta`. Switching naar iceberg vergt geen modelwijziging:
`TABLE_FORMAT=iceberg dbt run`.

## Lokaal draaien

```bash
cd dbt
export DBT_PROFILES_DIR="$(pwd)"     # of cp profiles.yml.template ~/.dbt/profiles.yml
cp profiles.yml.template profiles.yml
# Edit profiles.yml: TRINO_PASSWORD via secret-store

dbt deps
dbt parse                            # geen DB nodig
dbt compile                          # geen DB nodig
dbt run --select staging.persona     # Trino + bronze data nodig
dbt test
dbt docs generate                    # produceert manifest.json + catalog.json
```

## Tests

| Type | Locatie | Wat |
|---|---|---|
| Generic (custom) | `macros/test_*.sql` | `bsn_valid`, `iban_valid`, `lh_nummer_valid` |
| Generic (built-in + dbt-utils + dbt-expectations) | `models/*/_*.yml` | `unique`, `not_null`, `accepted_values`, `relationships`, `expect_*` |
| Singular | `tests/*.sql` | Custom business rules per UC |

## CGM-koppeling

Elk gold-mart heeft `meta.cgm_entiteit:` velden in `_*.yml`. OpenMetadata's
dbt-workflow (fase 8) leest deze meta en propageert ze naar de
data-catalog tags + glossary.

Lijst CGM-entiteiten zit in [`docs/use-cases/`](../docs/use-cases/) per UC.

## Compliance-velden in `meta:`

Elk model **moet** in zijn schema.yml een `meta:` block hebben met:

```yaml
meta:
  domain: ag                                    # divisie
  legal_basis: WIA_art_64                       # AVG art. 6 (en eventueel 9)
  doelbinding: [uitkering, reintegratie]
  bio_classificatie: vertrouwelijk              # publiek|intern|vertrouwelijk|geheim
  bewaartermijn_jaren: 7
  eigenaar: divisie_ag
  pii_kolommen: [bsn, birth_date]
  risk_tier: laag                               # laag|midden|hoog|verboden
```

Zie `docs/compliance-mapping.md` voor traceability per R-* eis.
