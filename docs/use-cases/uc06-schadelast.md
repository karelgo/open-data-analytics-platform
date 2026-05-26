# UC-06 — Schadelast- en uitkeringslastprognose (FEZ)

| Status in deze repo | **Volledig geïmplementeerd** (geaggregeerd) |
|---|---|
| Domein | FEZ |
| Risicoclassificatie | Laag (geaggregeerde data, geen PII in gold) |
| AVG-grondslag | Voornamelijk geanonimiseerd → buiten AVG-scope |
| Bewaartermijn | 10 jaar (begroting/realisatie) |

Bron: [`referentiearchitectuur-odap-data-analytics.md` § 8 UC-06](../../referentiearchitectuur-odap-data-analytics.md).

---

## Probleem

Begrotingscyclus en raming uitkeringslasten vereist actuele en goed onder-
bouwde prognoses. WIA-volume stijgt, afschaffing IVA staat ter discussie —
beleidsscenario's moeten doorgerekend kunnen worden.

## Doel

Actuariële modellen voor 5-jaars uitkeringslastprognose per wet, met
scenario-analyse.

## Data

| Bron | Inhoud |
|---|---|
| Geaggregeerde uitkeringsdata per wet | Volume, gemiddelde duur per wet (WW/WIA/Wajong/ZW/WAO/TW) |
| Demografische trends (CBS) | Beroepsbevolking, leeftijdspiramide |
| Economische indicatoren (CPB) | Werkloosheid, BBP-groei |
| Historische schadelast | 10 jaar terug |

**Geen herleidbare cliëntdata.** Alleen geaggregeerd of gepseudonimiseerd.

## Architectuur-pad

```
silver.fez.uitkeringslast_per_wet_per_maand
silver.referentie.cbs_macro
silver.referentie.cpb_indicatoren
            │
            ▼
mart_uc06_uitkeringslast_5y.sql (basis-projectie)
            │
            ├── tijdreeks via Spark-job ml_lastprognose.py (Prophet/statsforecast)
            │   output: gold.uc06_lastprognose.prognose_per_wet
            │
            └── scenario-engine (Trino-side `MERGE INTO` met scenario-parameters)
                output: gold.uc06_lastprognose.scenario_results
```

## Scenario-engine

`gold.uc06_lastprognose.scenario_inputs` bevat scenario-rijen:

| scenario_id | beschrijving | parameter | waarde |
|---|---|---|---|
| baseline | Niets verandert | n.v.t. | n.v.t. |
| iva_afschaf_2027 | IVA afgeschaft per 2027 | iva_volume_factor_2027 | 0.0 |
| ww_versoberen | WW max 12 mnd ipv 24 | ww_max_duur_mnd | 12 |

Trino-query produceert `scenario_results` met de gewijzigde projectie.

## dbt-model `meta`

```yaml
meta:
  domain: fez
  legal_basis: n/a   # geaggregeerd, geen persoonsgegevens
  doelbinding: [actuarie, beleid]
  bio_classificatie: intern
  bewaartermijn_jaren: 10
  eigenaar: divisie_fez
  pii_kolommen: []
  risk_tier: laag
  publiek_te_publiceren: true   # via UWV.nl en jaarverslag
```

## OPA-policies

- Toegang tot `gold.uc06_lastprognose.*` voor rollen `finance_analyst`,
  `data_steward`, `platform_admin`.
- Geen kolom-masks; geen row-filters (data is publiek-publiceerbaar).
- Wel: audit-log van wijzigingen aan `scenario_inputs` (kritisch voor
  reproduceerbaarheid van publicaties).

## OpenMetadata

- Tags: `Domain.FEZ`, `Aggregaat.geanonimiseerd`, `Doelbinding.actuarie`,
  `Public.true`.
- Glossary: `Schadelast`, `Uitkeringslast`, `Premie`, `Aof`, `Awf`, `Whk`,
  `Ufo`.

## Outputs

- `dbt/seeds/cbs_macro_synthetic.csv` (synthetische macro-trends).
- `dbt/seeds/cpb_indicatoren_synthetic.csv`.
- `dbt/seeds/scenario_inputs.csv` (initiële scenario's).
- `dbt/models/marts/uc06_lastprognose/{mart_uc06_uitkeringslast_5y.sql, mart_uc06_scenario_results.sql, schema.yml}`.
- `spark-jobs/ml_lastprognose.py` (Prophet-based tijdreeks; placeholder
  met simpele lineaire trend in deze referentie).
- `platform/12-superset/dashboards/uc06-lastprognose.json`.

## Open vragen

- Echte CBS-microdata vereist apart governance-regime; voor referentie
  voldoen synthetische trends.
- Reproduceerbaarheid van publicaties: hash van inputs + scenario opnemen
  in publicatie-PDF (out-of-scope dit referentieplatform).
