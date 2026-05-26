# UC-01 — WIA Funnel (sturingsinformatie)

| Status in deze repo | **Volledig geïmplementeerd** (DoD-anchor) |
|---|---|
| Domein | AG (WIA) |
| Risicoclassificatie | Laag (sturingsinfo, geen impact op individu) |
| AVG-grondslag | Art. 6 lid 1e (wettelijke taak); aggregaten zonder herleiding |
| Bewaartermijn (gold) | 7 jaar (besluitvormingsdata) |

Bron: [`referentiearchitectuur-odap-data-analytics.md` § 8 UC-01](../../referentiearchitectuur-odap-data-analytics.md).

---

## Probleem

WIA-aanvragen stegen sinds 2022 met 31%, afhandelingen met 19,4%; eind 2025
wachten ruim 12.000 mensen langer dan de wettelijke termijn. Capaciteits-
sturing van verzekeringsartsen en arbeidsdeskundigen is suboptimaal.

## Doel

Realtime inzicht in voorraad, doorlooptijden, wachtgelden (voorschotten) en
voorspelling van workload per regio en specialisme.

## Data

| Bron | Inhoud | Klassificatie |
|---|---|---|
| WIA-claimsysteem | Aanvraag, Beoordeling, status-historie | Vertrouwelijk (PII gepseudonimiseerd in stuurinfo) |
| SMZ capaciteitsplanning | Beoordelaar-roosters | Intern |
| FEZ voorschotbetalingen | Voorschot-uitkering per cliënt | Vertrouwelijk |
| Re-integratieverslagen | Plan van aanpak werkgever | Vertrouwelijk |

**CGM-entiteiten** (uit referentiearchitectuur): `Aanvraag`, `Beoordeling`,
`Beoordelaar`, `Cliënt` (gepseudonimiseerd in stuurinfo).

## Architectuur-pad in deze repo

```
synthetic-WIA-bron (data-generation/generators/wia.py)
     │
     ▼
NiFi: GenerateFlowFile + UpdateAttribute (PII-tag) + PublishKafka
     │
     ▼
Kafka topic: uwv.wia.aanvraag, uwv.wia.beoordeling
     │
     ▼
SparkApplication: streaming_kafka_to_lakehouse.py  →  bronze.uwv.wia_aanvraag, bronze.uwv.wia_beoordeling
                                                       (Delta, partition by event_date)
     │
     ▼
dbt staging: stg_wia_aanvraag.sql, stg_wia_beoordeling.sql  →  silver.wia.*
     │
     ▼
dbt mart: mart_uc01_wia_funnel_daily.sql  →  gold.uc01_wia_funnel.funnel_daily
     │
     ▼
Superset dashboard "WIA Funnel"
```

## dbt-model `meta`

```yaml
meta:
  domain: ag
  legal_basis: WIA_art_64
  doelbinding: [sturingsinfo]
  bio_classificatie: intern   # geaggregeerd
  bewaartermijn_jaren: 7
  eigenaar: divisie_ag
  pii_kolommen: []            # geaggregeerd, geen direct herleidbare PII
  risk_tier: laag
```

## OPA-policies (UC-relevant)

- Toegang tot `gold.uc01_wia_funnel.*` voor rollen `data_steward`, `claims_analyst`, `platform_admin`.
- Geen row filters nodig (data is regio-aggregaat); regio-filter is een UI-keuze.
- Geen kolom-masks (geen PII in gold).

## OpenMetadata

- Service: Trino → schema `gold.uc01_wia_funnel` ingest.
- Dashboard: Superset-service → "WIA Funnel" met lineage naar mart-tabel.
- Tags: `Domain.AG`, `Wet.WIA`, `Doelbinding.sturingsinfo`.
- Glossary-term: `Aanvraag` (CGM), gekoppeld aan kolom `aanvraag_id`.

## Outputs (artefacten in repo)

- `dbt/models/staging/wia/{stg_wia_aanvraag.sql, stg_wia_beoordeling.sql, schema.yml}`
- `dbt/models/marts/uc01_wia_funnel/{mart_uc01_wia_funnel_daily.sql, schema.yml}`
- `nifi-flows/templates/delta/wia-ingest.xml`
- `spark-jobs/streaming_kafka_to_lakehouse.py` (gedeeld met UC-03)
- `platform/12-superset/dashboards/uc01-wia-funnel.json`
- `tests/e2e/full-flow-uc01.sh` (DoD-test)

## Open vragen / TODO

- Voorspelmodel (gradient boosting) voor instroom-prognose: niet in fase 5;
  optionele uitbreiding (zie UC-06 voor tijdreeks-patroon).
