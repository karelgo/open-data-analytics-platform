# UC-05 — 360°-cliëntbeeld voor klantcontact (CRM)

| Status in deze repo | **Volledig geïmplementeerd** met OPA column-masks |
|---|---|
| Domein | CRM (cross-domein consumer) |
| Risicoclassificatie | Laag-midden (geen besluit, wel gevoelige aggregatie) |
| AVG-grondslag | Art. 6 lid 1e |
| Bewaartermijn | 7 jaar voor besluit-relaterende velden; 2 jaar voor klantcontactlogs |

Bron: [`referentiearchitectuur-odap-data-analytics.md` § 8 UC-05](../../referentiearchitectuur-odap-data-analytics.md).

---

## Probleem

Klanten met meerdere uitkeringen (WW + TW, WIA + Wajong, ...) worden nu door
medewerkers via meerdere systemen bediend. Werkmap, telefoon en balie hebben
geen samenhangend beeld. UWV-medewerkers zien teveel of te weinig — beide
zijn fout.

## Doel

Eén geïntegreerd cliëntbeeld voor UWV-medewerkers. **Doelbinding strikt**:
medewerker ziet alleen velden die nodig zijn voor diens rol/taak (column-level
ABAC).

## Data

| Bron | Inhoud |
|---|---|
| Polisadm + uitkeringssystemen | Lopende uitkeringen, status, bedragen |
| CRM | Klantcontactlogs, kanaalvoorkeur, klachten |
| Werkmap | Berichten, opt-out-keuzes |
| Re-integratie-applicatie | Lopende trajecten |

**CGM-entiteiten**: `Cliënt`, `Uitkering`, `Contact`, `Kanaal`.

## Architectuur-pad

```
silver.uitkeringen + silver.contacten + silver.werkmap_berichten + silver.trajecten
                                     │
                                     ▼
                      mart_uc05_client_360.sql  (denormalized view per BSN)
                                     │
                                     ▼
                       gold.uc05_client_360.client_overview
                                     │  (alle kolommen aanwezig, OPA filtert)
                                     ├── via Trino REST API → CRM/Werkmap
                                     │
                                     └── via Trino voor analisten (rol `data_steward`)
```

## OPA — kolomen-projectie per rol (kritiek voor deze UC)

| Kolom | `marketing_analyst` | `claims_analyst` | `fraud_analyst` | `data_steward` |
|---|---|---|---|---|
| `bsn` | masked (`'XXXXXXX' || substring(bsn, 8)`) | full | full | masked |
| `naam` | full | full | full | masked |
| `geboortedatum` | full | full | full | bucket per jaar |
| `adres` | regio-only | full | full | regio-only |
| `lopende_uitkeringen[]` | full (alle) | full | WW + handhaving-relevant | full |
| `medische_diagnose` | **deny** | full | **deny** | **deny** |
| `klantcontact_recent[]` | full | summary | summary | summary |
| `bankrekening` | masked | masked | full (handhaving) | masked |
| `klacht_status` | full | full | full | full |

Implementatie: `opa-policies-src/trino/trino-platform-roles.rego` +
`trino-column-masks.rego` + `trino-row-filters.rego`.

## dbt-model `meta`

```yaml
meta:
  domain: crm
  legal_basis: WIA+WW+Wajong+TW (cross)
  doelbinding: [klantcontact, behandeling]
  bio_classificatie: vertrouwelijk
  bewaartermijn_jaren: 7   # uitkering-velden
  bewaartermijn_klantcontact_jaren: 2
  eigenaar: divisie_crm
  pii_kolommen: [bsn, naam, adres, bankrekening, geboortedatum]
  risk_tier: laag-midden
  human_in_the_loop: true
  toegang_via_OPA_policies: true
```

## "Glass box logging"

Elke API-call (Trino read door CRM-applicatie) wordt gelogd met:

- gebruiker (Keycloak-claim `sub`)
- rol (Keycloak-claim `roles`)
- doelcode (HTTP header `X-Purpose`)
- aanleiding (HTTP header `X-Reason`, bv. `ticket-12345`)
- gequeried `bsn`
- timestamp

Geleverd via Trino event-listener → Kafka topic `uwv.audit.client_360` → Spark
batch naar `bronze.audit.client_360_reads` (Delta, retention 7 jaar).

## OpenMetadata

- Tags: `Domain.CRM`, `Doelbinding.klantcontact`, `Doelbinding.behandeling`,
  `PII.Sensitive`, `AccessControl.OPA`.
- Per kolom een specifieke `Doelbinding.*` tag — voedt OPA policies via
  reverse-metadata pad (TODO in fase 8).

## Outputs

- `dbt/models/marts/uc05_client_360/{mart_uc05_client_360.sql, schema.yml}`.
- `opa-policies-src/trino/trino-column-masks.rego`.
- `opa-policies-src/trino/trino-row-filters.rego` (regio-filter).
- `tests/integration/test_uc05_role_projections.sh` — controleert per
  Keycloak-rol welke kolommen visible zijn.

## Quarterly access review

Stap-voor-stap procedure (out-of-scope productie):

1. OPA-bundle dump van actieve role-mappings.
2. Cross-check met Keycloak realm-export.
3. Manager-bevestiging per medewerker dat rollen nog passen bij taak.

In deze referentie: enkel een placeholder-script `scripts/access-review-dump.sh`.
