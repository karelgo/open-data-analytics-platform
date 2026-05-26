# UC-11 — Integrale Klantreis (event-stream + fase-reconstructie)

| Status in deze repo | **Volledig geïmplementeerd** (presentatie-anchor) |
|---|---|
| Domein | Cross-domein (persoon, polisadm, ww, zw, wia, wajong, crm) |
| Risicoclassificatie | Laag-midden (geen besluit, wel cross-domein aggregatie) |
| AVG-grondslag | Art. 6 lid 1e (publieke taak) — gecombineerd uit wettelijke grondslag per bron |
| Bewaartermijn | Erft langste bewaartermijn van bronnen (30 jaar — polisadm) |

Bron-aanvulling: deze UC is **niet** in `referentiearchitectuur-odap-data-analytics.md`
beschreven. Toegevoegd in deze referentie-implementatie als **integrale demo**
die alle platform-facetten in één klantverhaal samenbrengt.

---

## Probleem

platform-cliënten doorlopen vaak meerdere wetten en domeinen: werknemer → ziek →
WIA-aanvraag → re-integratie → werkhervatting → bezwaar. Vandaag zien
medewerkers **fragmenten** per systeem (Werkmap, polisadm, CRM, WIA-claim).
Een **temporele**, **cross-domein** klantreis bestaat niet — terwijl die
informatie wel in de bronsystemen aanwezig is, alleen nooit als
event-stream is gemodelleerd.

UC-05 (Cliënt 360) lost een ander probleem op: het toont **wat nu geldt**
voor één cliënt (statische snapshot). UC-11 toont **hoe iemand hier is
gekomen**: een tijdlijn van fase-overgangen, met doorlooptijden,
kanalen en uitkomsten.

## Doel

Twee samenhangende data products in `gold.uc11_klantreis`:

1. **`mart_uc11_klantreis_events`** — denormalized event-stream met één rij
   per gebeurtenis (`bsn`, `event_ts`, `domein`, `event_type`, `label`, ...).
   Bron voor klantreis-tijdlijn-visualisaties in Superset + voor downstream
   API-consumptie door CRM-applicaties.
2. **`mart_uc11_klantreis_phases`** — gereconstrueerde fasen per cliënt via
   gaps-and-islands (`werknemer` → `ziek` → `wia_in_behandeling` → `wga` →
   `re_integratie` → `werkhervatter`), met doorlooptijden en
   eind-uitkomsten.

**Doelbinding strikt**: dezelfde gold-tabel levert per rol een ander
verhaal. OPA filtert kolommen + rijen at-query-time; er bestaat geen
"klantreis-met-volledige-PII"-view.

## Data — bronnen en CGM-entiteiten

| Bron (silver) | Bijdrage aan klantreis | CGM-entiteit |
|---|---|---|
| `silver.persoon.stg_persona` | Geboorte van cliënt-record, NAW | `Cliënt`, `Persona` |
| `silver.polisadm.stg_polisadm_ikv` | Dienstverband-aanvang/einde, inkomen | `IKV`, `Werknemer`, `Werkgever`, `Dienstverband`, `Ontslag` |
| `silver.ww.stg_ww_aanvraag` | WW-aanvraag, reden ontslag, status-overgang | `Aanvraag`, `Uitkering` |
| `silver.zw.stg_zw_melding` | Ziekmelding, duur ziektewet | `Aanvraag` |
| `silver.wia.stg_wia_aanvraag` | WIA-aanvraag, ao-percentage, regio, status | `Aanvraag`, `Beoordeling`, `Uitkering` |
| `silver.wajong.stg_wajong_dossier` | Wajong-regime, arbeidsvermogen | `Aanvraag`, `Uitkering` |
| `silver.crm.stg_crm_contact` | Klantcontact-events per kanaal | `Contact`, `Kanaal` |

**Geen** nieuwe bron-generator — de klantreis is een **derivaat** van
bestaande gegenereerde events. Dat is een bewuste designkeuze: het
demonstreert dat het platform de informatie al heeft; UC-11 ontsluit het
alleen.

## Architectuur-pad in deze repo

```
silver.<domain>.stg_*  (7 staging-views; bestaande modellen, ongewijzigd)
                │
                ▼
   silver.intermediate.int_klantreis_events   (view: UNION ALL → unified schema)
                │
                ├──►  gold.uc11_klantreis.mart_uc11_klantreis_events  (table; één rij per gebeurtenis)
                │
                └──►  gold.uc11_klantreis.mart_uc11_klantreis_phases  (table; gaps-and-islands)
                                                  │
                       ┌──────────────────────────┼──────────────────────────┐
                       ▼                          ▼                          ▼
                Superset dashboard       Trino REST API → CRM-app    OpenMetadata lineage
                "Klantreis-tijdlijn"     (Purpose-header verplicht)  (per kolom Doelbinding-tag)
```

Auth/authz/audit-pad (cross-cutting, ongewijzigd t.o.v. UC-05):

```
Keycloak (OIDC, rol-claim) ──► Trino ──► OPA bundle ──► allow + rowFilters + columnMask
                                                             │
                                                             ▼
                              Trino event-listener ──► Kafka uwv.audit.klantreis
                                                             │
                                                             ▼
                                            Spark batch ──► bronze.audit.klantreis_reads (Delta, 7y)
```

## Event-schema (uniform over alle domeinen)

| Kolom | Type | Omschrijving |
|---|---|---|
| `bsn` | varchar | Eigenaar van de gebeurtenis (gemaskeerd per OPA-mask) |
| `event_ts` | timestamp | Domein-specifieke gebeurtenistijd (val. terug op `event_date`) |
| `event_date` | date | Partitie-veld (uit bronze) |
| `domein` | varchar | `persoon` / `polisadm` / `ww` / `zw` / `wia` / `wajong` / `crm` |
| `event_type` | varchar | bv. `polisadm.ikv.start`, `wia.aanvraag.toegekend_wga`, `crm.contact` |
| `event_label` | varchar | Mens-leesbaar (`"Dienstverband begonnen bij ACME B.V."`) |
| `event_status` | varchar | bv. `INGEDIEND`, `TOEGEKEND_WGA`, of `NULL` |
| `regio_code` | varchar | Voor row-filter; alleen WIA vult deze |
| `numeric_value` | double | bv. `arbeidsongeschikt_pct`, `loon_bruto_jaar` |
| `source_ref_id` | varchar | Originele primary key (`aanvraag_id`, `ikv_id`, ...) — voor audit |

## Fase-reconstructie (gaps-and-islands)

Vanuit `mart_uc11_klantreis_events` worden **fasen** afgeleid:

| Fase | Trigger-event | Eindigt bij |
|---|---|---|
| `werknemer` | `polisadm.ikv.start` (eerste of nieuwe) | `polisadm.ikv.einde` of nieuwe fase |
| `ziek` | `zw.melding` | `ziek + duur_dagen` of WIA-aanvraag |
| `ww_aanvraag` | `ww.aanvraag.ingediend` | `ww.aanvraag.toegekend` of `_afgewezen` |
| `ww_uitkering` | `ww.aanvraag.toegekend` | nieuw IKV-start of einde reeks |
| `wia_in_behandeling` | `wia.aanvraag.ingediend` | `wia.aanvraag.toegekend_*` of `_afgewezen` |
| `wga` | `wia.aanvraag.toegekend_wga` | nieuw IKV-start |
| `iva` | `wia.aanvraag.toegekend_iva` | — (geen einde in synthetische data) |
| `wajong_actief` | `wajong.dossier.geopend` | — |
| `werkhervatter` | `polisadm.ikv.start` ná WGA/IVA-fase | volgende fase |

Implementatie via window-functions (`row_number()`, `lag()`) over
`event_ts` per `bsn`.

## OPA — kolom-projectie en row-filter per rol (kritiek voor de demo)

Eén query op `gold.uc11_klantreis.mart_uc11_klantreis_events`, acht
weergaves. Volledige matrix in `opa-policies-src/trino/`:

| Kolom | `crm_medewerker` | `wia_beoordelaar` | `ww_handhaver` | `wajong_arbeidsdeskundige` | `fez_analist` | `data_steward` |
|---|---|---|---|---|---|---|
| `bsn` | masked (last-4) | full | full | full | hashed | bucket |
| `event_label` | sanitized (geen diagnose) | full | full | full | aggregated | sanitized |
| `event_type` | full | full | medisch=deny | full | full | full |
| `numeric_value` | full (geen medisch) | full | full | full | full (geen medisch) | full |
| `regio_code` | full | row-filter own | full | full | full | full |
| `source_ref_id` | masked | full | full | full | masked | masked |

**Row-filters:**
- `wia_beoordelaar` met `extraCredentials.regio=AMS` → `regio_code = 'AMS' OR regio_code IS NULL`
- `klantreis_demo_persona` capability → `bsn = 'XXXXX-XXX01'` (voor presentatie-modus, één persona)
- `ww_handhaver` → medische event-types weggefilterd (`domein != 'wia' OR event_status != 'TOEGEKEND_IVA'`)

Implementatie:
- `opa-policies-src/trino/trino-row-filters.rego` — regel toegevoegd voor `schemaName = 'uc11_klantreis'`.
- `opa-policies-src/trino/trino-column-masks.rego` — bestaande masks (`bsn`, `geboortedatum`) gelden vanzelf; UC-11-specifieke mask op `event_label` voor non-medische rollen.

## dbt-model `meta`

```yaml
meta:
  domain: cross
  legal_basis: AVG_art_6_1e   # publieke taak, gecombineerd
  doelbinding: [klantcontact, behandeling, sturingsinfo]
  bio_classificatie: vertrouwelijk
  bewaartermijn_jaren: 30     # langste van bronnen (polisadm)
  eigenaar: divisie_klantcontact   # primair consumer; cross-domein-product
  pii_kolommen: [bsn, event_label, source_ref_id]
  risk_tier: laag-midden
  human_in_the_loop: true
  toegang_via_OPA_policies: true
  cgm_entiteiten: [Cliënt, IKV, Aanvraag, Beoordeling, Uitkering, Contact, Kanaal]
```

## "Glass box logging"

Elke read op `gold.uc11_klantreis.*` door een externe applicatie wordt via
de bestaande Trino event-listener gelogd. Audit-record bevat:

- gebruiker (Keycloak `sub`)
- rol (Keycloak `roles`)
- doelcode (HTTP header `X-Trino-Extra-Credential: purpose=klantcontact`)
- aanleiding (`X-Trino-Extra-Credential: reason=ticket-12345`)
- gequeried BSN (uit WHERE-clause; pseudonimiseerd in audit-log)
- timestamp + applied-row-filter + applied-column-mask

Pad: Trino event-listener → Kafka `uwv.audit.klantreis` → Spark batch →
`bronze.audit.klantreis_reads` (Delta, retentie 7 jaar).

## OpenMetadata

- Service: Trino → schema `gold.uc11_klantreis` ingest.
- Dashboard: Superset-service → "Klantreis-tijdlijn" met lineage naar marts.
- Tags: `Domain.Cross`, `Doelbinding.Klantcontact`, `Doelbinding.Behandeling`,
  `Doelbinding.Sturingsinfo`, `PII.Sensitive`, `AccessControl.OPA`.
- Glossary-koppeling: nieuwe term `Klantreis` (cross-CGM aggregaat).
- Per kolom een specifieke `Doelbinding.*`-tag — voedt OPA via
  reverse-metadata pad.

## Outputs (artefacten in repo)

- `dbt/models/intermediate/int_klantreis_events.sql` + entry in `_intermediate.yml`.
- `dbt/models/marts/uc11_klantreis/{mart_uc11_klantreis_events.sql, mart_uc11_klantreis_phases.sql, _uc11.yml}`.
- `dbt_project.yml` — schema-config voor `uc11_klantreis`.
- `opa-policies-src/trino/trino-row-filters.rego` — UC-11 row filter.
- `opa-policies-src/trino/trino-column-masks.rego` — UC-11 `event_label` mask.
- `opa-policies-src/trino/trino-row-filters_test.rego` + `trino-column-masks_test.rego` — uitbreiding.
- `platform/11-airflow/include/gold_factory.py` — UC-11 in `ACTIVE_USE_CASES`.
- Source-YAMLs (`platform/11-airflow/sources/*.yml`) — `used_by_use_cases += uc11`.
- `platform/13-openmetadata-config/glossary-cgm.yaml` — term `Klantreis`.
- `tests/smoke/11-uc11-klantreis.sh` — dbt-parse + OPA-decisions voor UC-11.
- `tests/e2e/uc11-flow.sh` — end-to-end (cluster vereist).
- `Makefile` — `make dbt-build-uc11`, `make test-uc11`.

## Presentatie-leidraad (10 slides)

1. **De cliënt** — Saskia Bakker, 47 jaar, BSN 99999-901. Cartoon-tijdlijn werknemer → ziek → WIA → re-integratie → werkhervatter.
2. **Eén tabel, acht waarheden** — dezelfde gold-tabel door zes rol-brillen (uit OPA-matrix hierboven).
3. **Dataflow** — generators → NiFi → Kafka → Spark → Delta → dbt → Trino → Superset (uit `docs/architecture.md` §1).
4. **Medallion + sensitive** — vier zones, waarom (uit `docs/architecture.md` §3).
5. **dbt-lineage** — staging × 7 → intermediate → 2 marts. Toon `dbt docs` lineage-graaf.
6. **Doelbinding als code** — OpenMetadata tag → OPA Rego → Trino-query-resultaat. Live demo van één query met `purpose=klantcontact` vs. zonder.
7. **AI-laag (minimaal)** — "next best contact" heuristiek; AI Act-classificatie `Laag`; algoritmeregister-stub.
8. **Audit demo** — `crm_medewerker` probeert WIA-medische details te zien → OPA deny → 30s later in audit-dashboard.
9. **Access-request** — nieuwe verzekeringsarts wil toegang tot `sensitive.wia.medisch_dossier` → OM-bridge → Keycloak realm-role.
10. **Wat dit kost** — k3d cluster, één `make` commando, geen cloud-bill.

## Open vragen / TODO

- Het fase-model gebruikt vereenvoudigde regels; productie zou state-machine
  per cliënt nodig hebben (Spark Structured Streaming met stateful
  aggregation). Voor demo-doeleinden voldoende.
- Audit-Kafka-topic `uwv.audit.klantreis` is symmetrisch met de bestaande
  `uwv.audit.client_360`. Eén Spark-job kan beide consumeren (out-of-scope).
- "Saskia"-persona wordt nu **gevonden** in de mart (BSN met meest diverse
  events). Voor reproducerbare demo: in een volgende iteratie een dbt seed
  `seeds/uc11_demo_personas.csv` met deterministische test-BSN's.

## Quarterly access review

Stap-voor-stap (zelfde patroon als UC-05):

1. OPA-bundle dump van actieve role-mappings.
2. Cross-check met Keycloak realm-export.
3. Manager-bevestiging per medewerker dat rollen nog passen bij taak.
4. Steekproef op audit-log: vergelijk `purpose=` waarden met
   feitelijke ticket-IDs.

Placeholder-script `scripts/access-review-dump.sh` (gedeeld met UC-05).
