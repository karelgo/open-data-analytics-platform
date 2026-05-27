# UC-06 — Cost forecast- en claim_costprognose (FEZ)

| Status in deze repo | **Volledig geïmplementeerd** (geaggregeerd) |
|---|---|
| Domein | FEZ |
| Risicoclassificatie | Laag (geaggregeerde data, geen PII in gold) |
| AVG-grondslag | Voornamelijk geanonimiseerd → buiten AVG-scope |
| Retention period | 10 jaar (begroting/realisatie) |

Bron: [`referentiearchitecture-odap-data-analytics.md` § 8 UC-06](../../referentiearchitecture-odap-data-analytics.md).

---

## Probleem

Begrotingscyclus en raming claim_costen vereist actuele en goed onder-
bouwde prognoses. WIA-volume stijgt, afschaffing IVA staat ter discussie —
beleidsscenario's moeten doorgerekend kunnen worden.

## Doel

Actuariële models voor 5-jaars claim_costprognose per wet, met
scenario-analyse.

## Data

| Bron | Inhoud |
|---|---|
| Geaggregeerde claim payoutsdata per wet | Volume, gemiddelde duur per wet (WW/WIA/Wajong/ZW/WAO/TW) |
| Demografische trends (CBS) | Beroepsbevolking, leeftijdspiramide |
| Economische indicatoren (CPB) | Werkloosheid, BBP-groei |
| Historische cost forecast | 10 jaar terug |

**Geen herleidbare cliëntdata.** Alleen geaggregeerd of gepseudonimiseerd.

## Architecture-pad

```
silver.finance.expense_per_wet_per_maand
silver.referentie.cbs_macro
silver.referentie.cpb_indicatoren
            │
            ▼
mart_uc06_cost_5y.sql (basis-projectie)
            │
            ├── tijdreeks via Spark-job ml_cost forecast.py (Prophet/statsforecast)
            │   output: gold.uc06_cost_forecast.prognose_per_wet
            │
            └── scenario-engine (Trino-side `MERGE INTO` met scenario-parameters)
                output: gold.uc06_cost_forecast.scenario_results
```

## Scenario-engine

`gold.uc06_cost_forecast.scenario_inputs` bevat scenario-rijen:

| scenario_id | beschrijving | parameter | waarde |
|---|---|---|---|
| baseline | Niets verandert | n.v.t. | n.v.t. |
| iva_afschaf_2027 | IVA afgeschaft per 2027 | iva_volume_factor_2027 | 0.0 |
| ww_versoberen | WW max 12 mnd ipv 24 | ww_max_duur_mnd | 12 |

Trino-query produceert `scenario_results` with the gewijzigde projectie.

## dbt-model `meta`

```yaml
meta:
  domain: fez
  legal_basis: n/a   # geaggregeerd, geen persoonsgegevens
  purpose-limitation: [actuarie, beleid]
  bio_classificatie: intern
  retention period_jaren: 10
  eigenaar: divisie_fez
  pii_kolommen: []
  risk_tier: laag
  publiek_te_publiceren: true   # via UWV.nl en jaarverslag
```

## OPA-policies

- Access tot `gold.uc06_cost_forecast.*` voor rollen `finance_analyst`,
  `data_steward`, `platform_admin`.
- Geen kolom-masks; geen row-filters (data is publiek-publiceerbaar).
- Wel: audit-log van wijzigingen aan `scenario_inputs` (kritisch voor
  reproduceerbaarheid van publicaties).

## OpenMetadata

- Tags: `Domain.FEZ`, `Aggregaat.geanonimiseerd`, `Purpose limitation.actuarie`,
  `Public.true`.
- Glossary: `Cost forecast`, `Claim payoutslast`, `Premie`, `Aof`, `Awf`, `Whk`,
  `Ufo`.

## Outputs

- `dbt/seeds/cbs_macro_synthetic.csv` (synthetische macro-trends).
- `dbt/seeds/cpb_indicatoren_synthetic.csv`.
- `dbt/seeds/scenario_inputs.csv` (initiële scenario's).
- `dbt/models/marts/uc06_cost_forecast/{mart_uc06_cost_5y.sql, mart_uc06_scenario_results.sql, schema.yml}`.
- `spark-jobs/ml_cost forecast.py` (Prophet-based tijdreeks; placeholder
  met simpele lineaire trend in deze referentie).
- `platform/12-superset/dashboards/uc06-cost-forecast.json`.

## Open vragen

- Echte CBS-microdata vereist apart governance-regime; voor referentie
  voldoen synthetische trends.
- Reproduceerbaarheid van publicaties: hash van inputs + scenario opnemen
  in publicatie-PDF (out-of-scope dit referentieplatform).
