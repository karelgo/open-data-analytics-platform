# UC-08 — Capaciteitsplanning sociaal-medische beoordelingen

| Status in deze repo | **Spec + dbt-mart skelet** (geen OR-Tools optimizer) |
|---|---|
| Domein | AG (SMZ) |
| Risicoclassificatie | Laag (interne planning, geen besluit over individu) |
| AVG-grondslag | Art. 6 lid 1b (arbeidsovereenkomst medewerker) + 1f (gerechtvaardigd belang) |
| Bewaartermijn | 5 jaar (planning-historie) |

Bron: [`referentiearchitectuur-odap-data-analytics.md` § 8 UC-08](../../referentiearchitectuur-odap-data-analytics.md).

---

## Probleem

Tekort aan verzekeringsartsen → wachtlijsten WIA en Wajong. Planning gebeurt
deels handmatig.

## Doel

Geoptimaliseerde toewijzing van beoordelingen aan beoordelaars op basis van
expertise, locatie, complexiteit en wachttijd. **Voorgestelde** planning
naar planners; menselijk akkoord verplicht.

## Data

| Bron | Inhoud |
|---|---|
| Roosters verzekeringsartsen / arbeidsdeskundigen | Beschikbaarheid per dag |
| Dossier-complexiteit (gederiveerd) | Categorieën A/B/C |
| Cliëntlocatie-voorkeuren | Regio + reisbereidheid |
| Doorlooptijd-targets per wet | Wettelijke termijnen |

**CGM-entiteiten**: `Beoordelaar`, `Capaciteit`, `Aanvraag`.

## Architectuur-pad (in deze repo: voorbereiding-mart, geen optimizer)

```
silver.smz.beoordelaar_rooster
silver.smz.dossier_complexiteit
silver.wia.aanvraag (open dossiers)
silver.wajong.aanvraag (open dossiers)
                       │
                       ▼
       mart_uc08_capaciteit_dagelijks.sql
                       │
                       ▼
       gold.uc08_smz_capaciteit.capaciteit_dagelijks
                       │
                       ▼
       Spark-job optimize_smz_planning.py (TODO — niet in fase 5)
       OR-Tools constrained optimization → werklijst per dag
                       │
                       ▼
       Planner-tool: voorgestelde planning + menselijk akkoord (out-of-scope)
```

## Mart-output (zonder optimizer)

`gold.uc08_smz_capaciteit.capaciteit_dagelijks`:

| datum | regio | specialisme | open_dossiers | beschikbare_uren | wachttijd_dagen_med | wachttijd_dagen_p95 |

Volstaat voor dashboards en handmatige planning. De optimizer (OR-Tools)
schrijft een werklijst die niet onder dbt valt — dat blijft Spark.

## dbt-model `meta`

```yaml
meta:
  domain: ag_smz
  legal_basis: arbeidsovereenkomst+gerechtvaardigd_belang
  doelbinding: [planning]
  bio_classificatie: intern
  bewaartermijn_jaren: 5
  eigenaar: divisie_ag_smz
  pii_kolommen: []   # cliënt-data is gepseudonimiseerd of niet aanwezig in mart
  risk_tier: laag
  human_approval_required: true
```

## OPA-policies

- Toegang tot `gold.uc08_smz_capaciteit.*` voor rol `operations_manager` +
  `data_steward`.
- Geen PII in mart → geen kolom-masks nodig.
- Cliëntdata in onderliggende silver-tabellen blijft onder strikte access.

## OpenMetadata

- Tags: `Domain.AG_SMZ`, `Doelbinding.planning`, `InternalOnly.true`.

## Outputs

- `dbt/models/staging/smz/{stg_smz_rooster.sql, stg_smz_complexiteit.sql, schema.yml}`.
- `dbt/models/marts/uc08_smz_capaciteit/{mart_uc08_capaciteit_dagelijks.sql, schema.yml}`.
- TODO `spark-jobs/optimize_smz_planning.py` (niet in fase 5).

## Open vragen / TODO

- OR-Tools optimizer ontwerpen + tunen — vereist domein-input van planners.
- Feedback-loop "planner markeert slechte voorstellen → model leert" buiten
  scope referentie.
