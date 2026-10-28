# UC-01 — WIA Funnel (sturingsinformatie)

| Status in deze repo | **Volledig geïmplementeerd** (DoD-anchor) |
|---|---|
| Domein | AG (WIA) |
| Risicoclassificatie | Laag (sturingsinfo, geen impact op individu) |
| AVG-grondslag | Art. 6 lid 1e (wettelijke taak); aggregaten zonder herleiding |
| Retention period (gold) | 7 jaar (besluitvormingsdata) |

Bron: [`referentiearchitecture-odap-data-analytics.md` § 8 UC-01](../../referentiearchitecture-odap-data-analytics.md).

---

## Probleem

WIA-request stegen sinds 2022 met 31%, afhandelingen met 19,4%; eind 2025
wachten ruim 12.000 mensen langer dan de wettelijke termijn. Capaciteits-
sturing van verzekeringsartsen en arbeidsdeskundigen is suboptimaal.

## Doel

Realtime inzicht in voorraad, doorlooptijden, wachtgelden (voorschotten) en
voorspelling van workload per regio en specialisme.

## Data

| Bron | Inhoud | Klassificatie |
|---|---|---|
| WIA-claimsysteem | Aanvraag, Assessment, status-historie | Vertrouwelijk (PII gepseudonimiseerd in stuurinfo) |
| SMZ capacity planning | Beoordelaar-roosters | Intern |
| FEZ voorschotbetalingen | Voorschot-claim payout per cliënt | Vertrouwelijk |
| Reintegrationverslagen | Plan van aanpak werkgever | Vertrouwelijk |

**CGM-entiteiten** (uit referentiearchitecture): `Aanvraag`, `Assessment`,
`Beoordelaar`, `Cliënt` (gepseudonimiseerd in stuurinfo).

## Architecture-pad in deze repo

```
synthetic-WIA-bron (data-generation/generators/wia.py)
     │
     ▼
NiFi: GenerateFlowFile + UpdateAttribute (PII-tag) + PublishKafka
     │
     ▼
Kafka topic: claims.application, uwv.wia.beoordeling
     │
     ▼
SparkApplication: streaming_kafka_to_lakehouse.py  →  bronze.claims.application, bronze.demo.wia_beoordeling
                                                       (Delta, partition by event_date)
     │
     ▼
dbt staging: stg_claim_application.sql, stg_wia_beoordeling.sql  →  silver.claims.*
     │
     ▼
dbt mart: mart_uc01_claims_funnel_daily.sql  →  gold.uc01_claims_funnel.funnel_daily
     │
     ▼
Superset dashboard "WIA Funnel"
```

## dbt-model `meta`

```yaml
meta:
  domain: ag
  legal_basis: WIA_art_64
  purpose-limitation: [sturingsinfo]
  bio_classificatie: intern   # geaggregeerd
  retention period_jaren: 7
  eigenaar: divisie_ag
  pii_kolommen: []            # geaggregeerd, geen direct herleidbare PII
  risk_tier: laag
```

## OPA-policies (UC-relevant)

- Access tot `gold.uc01_claims_funnel.*` voor rollen `data_steward`, `claims_analyst`, `platform_admin`.
- Geen row filters nodig (data is regio-aggregaat); regio-filter is een UI-keuze.
- Geen kolom-masks (geen PII in gold).

## OpenMetadata

- Service: Trino → schema `gold.uc01_claims_funnel` ingest.
- Dashboard: Superset-service → "WIA Funnel" met lineage naar mart-tabel.
- Tags: `Domain.AG`, `Wet.WIA`, `Purpose limitation.sturingsinfo`.
- Glossary-term: `Aanvraag` (CGM), gekoppeld aan kolom `application_id`.

## Outputs (artefacten in repo)

- `dbt/models/staging/wia/{stg_claim_application.sql, stg_wia_beoordeling.sql, schema.yml}`
- `dbt/models/marts/uc01_claims_funnel/{mart_uc01_claims_funnel_daily.sql, schema.yml}`
- `nifi-flows/templates/delta/wia-ingest.xml`
- `spark-jobs/streaming_kafka_to_lakehouse.py` (gedeeld met UC-03)
- `platform/12-superset/dashboards/uc01-claims-funnel.json`
- `tests/e2e/full-flow-uc01.sh` (DoD-test)

## Open vragen / TODO

- Voorspelmodel (gradient boosting) voor instroom-prognose: niet in fase 5;
  optionele uitbreiding (zie UC-06 voor tijdreeks-patroon).
