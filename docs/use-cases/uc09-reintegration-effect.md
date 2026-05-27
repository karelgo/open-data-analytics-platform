# UC-09 — Effectmeting re-integratie-instrumenten

| Status in deze repo | **Sandbox-spec** — gepseudonimiseerd panel + stub-mart |
|---|---|
| Domein | AG / WW / Wajong / Re-integratie |
| Risicoclassificatie | Laag (verenigbaar gebruik wetenschappelijk/statistisch) |
| AVG-grondslag | Art. 5 lid 1b (verenigbaar gebruik voor wetenschappelijk/statistisch doel) |
| Bewaartermijn | Zo lang als nodig voor de studie + publicatie-archief |

Bron: [`referentiearchitectuur-odap-data-analytics.md` § 8 UC-09](../../referentiearchitectuur-odap-data-analytics.md).

---

## Probleem

UWV zet jaarlijks honderden miljoenen in op re-integratie (sollicitatie-
training, scholing, IPS, proefplaatsingen, jobcoaching). Welke instrumenten
werken voor welke doelgroep?

## Doel

Causale-inferentie analyses (quasi-experimentele methoden, propensity score
matching) op effectiviteit per instrument × doelgroep. Resultaten gepubliceerd
in `odap.io/kennis`.

## Data

| Bron | Inhoud |
|---|---|
| Re-integratiedossier | Trajecten per cliënt |
| Polisadministratie | Post-traject werk-status, dagloon |
| Wajong/WIA-status | Dossierhistorie |
| Demografie (gepseudonimiseerd) | Leeftijd, regio, opleidingsniveau |
| Kosten per traject | Re-integratiebudget |

**CGM-entiteiten**: `Traject`, `Uitkomst`, `Cliënt` (gepseudonimiseerd).

## Architectuur-pad

```
silver.reint.traject + silver.policies.werkstatus + silver.demografie_pseudo
                        │
                        ▼
   mart_uc09_effect_panel.sql (gepseudonimiseerd panel, no re-id)
                        │
                        ▼
   sandbox MinIO bucket: sandbox/uc09/
                        │
                        ▼
   Jupyter / SparkApplication: causalml-pipelines (DoWhy, propensity scoring)
                        │
                        ▼
   Output: rapport-PDF + figures (publiek)
```

## Sandbox-isolatie

UC-09 draait in een **aparte zone** met striktere regels:

- Eigen MinIO-bucket `sandbox` (schaduw van silver, alleen pseudo-IDs).
- Eigen Trino-schema `sandbox.uc09_*`.
- Geen herleidbaarheid naar individu via key-lookup; pseudo-ID is
  one-way-hash + zout.
- Researcher-rol heeft geen toegang tot productie-silver/gold.

## dbt-model `meta`

```yaml
meta:
  domain: ag
  legal_basis: art_5_1b_verenigbaar_gebruik
  doelbinding: [statistisch_onderzoek]
  bio_classificatie: intern
  bewaartermijn_jaren: 10  # studie-archief
  eigenaar: knowledge_center
  pii_kolommen: [bsn_pseudo]   # alleen pseudo
  risk_tier: laag
  sandbox_only: true
  publicatie_doel: odap.io/kennis
```

## OPA-policies

- Toegang tot `sandbox.uc09_*` alleen voor rol `researcher` (bestaat in
  Keycloak realm, niet voor productie-rollen).
- Geen access naar `gold.uc05_*` of `silver.customers.*` voor researcher.
- DPIA voor onderzoekspijplijn als verplichte attachment in OM
  (`Doelbinding.statistisch_onderzoek` tag impliceert DPIA-aanwezigheid).

## OpenMetadata

- Tags: `Sandbox.true`, `Doelbinding.statistisch_onderzoek`,
  `Pseudonymized.true`, `LegalBasis.art_5_1b`.

## Outputs

- `dbt/models/marts/uc09_reintegration_effect/{mart_uc09_effect_panel.sql, schema.yml}` (in `sandbox`-target).
- `data-generation/generators/reintegratie.py` voor synthetische trajecten.
- `spark-jobs/uc09_propensity_score_demo.py` (placeholder met DoWhy-import-stub).

## Open vragen / TODO

- DPIA-template invullen — out of scope referentie.
- Reproduceerbaarheid: studie-runs hashen + opnemen in publicatie-archief.
