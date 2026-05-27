# UC-03 — WW "verwijtbaar werkloos"-risicomodel (vernieuwde versie)

| Status in deze repo | **Spec + dbt-mart skelet** (geen ML-training in fase 5) |
|---|---|
| Domein | WW |
| Risicoclassificatie | **Hoog (AI Act)** — access tot claim payout |
| AVG-grondslag | Art. 6 lid 1e |
| Retention period | 7 jaar |

Bron: [`referentiearchitecture-odap-data-analytics.md` § 8 UC-03](../../referentiearchitecture-odap-data-analytics.md).

---

## Context

UWV gebruikt een risicomodel voor WW-request. De Algemene Rekenkamer (mei
2025) oordeelde dat het model 3× effectiever is dan willekeurige controle en
"grotendeels op orde", maar IT-beheer van de risicoscan vraagt aandacht.
Doel hier: **nieuwe versie** op moderne MLOps-stack met sterkere monitoring
en uitlegbaarheid.

## Doel

Triagering: model selecteert WW-dossiers voor handmatige controle op
verwijtbaarheid; behandelaar beslist daadwerkelijk over verwijtbaarheid.

## Data

| Bron | Inhoud |
|---|---|
| WW-aanvraag | Aanvraag, opzeggingsdocumenten (NLP-extractie) |
| Polisadministratie | Arbeidsverleden, dagloon |
| Eerdere uitkomsten verwijtbaarheidstoets | Label voor supervised learning |

**CGM-entiteiten**: `Aanvraag`, `Dienstverband`, `Ontslag`.

## Architecture-pad

```
NiFi: PublishKafka service_requests.application
     │
     ▼
Spark Streaming  →  bronze.service_requests.application (Delta)
     │
     ▼
dbt staging: stg_service_request_application, stg_ww_opzegging  →  silver.service_requests.*
     │
     ▼
dbt mart: mart_uc03_verwijtbaar_signalen  →  gold.uc03_fraud_risk.signalen_dagelijks
     │
     ├── Inputs voor model-training (fase 5+, niet in deze repo geïmplementeerd)
     │
     └── Behandelaar-werklijst (Trino → API → werklijst-UI, out-of-scope)
```

In deze referentie: **`gold.uc03_fraud_risk.signalen_dagelijks`** is een
regel-gebaseerde signalering, niet ML. Voorbeelden van signalen:

- `signaal_ontslag_op_staande_voet` (boolean)
- `signaal_geen_sollicitaties_4w` (boolean)
- `signaal_korte_dienstverbanden_3y` (count)
- `verwijtbaarheid_score_hint` (0..1, eenvoudige weighted sum, **niet** een
  ML-prediction)

Een echt ML-model komt via dezelfde patterns als UC-02 (Sensitive Vault niet
nodig — geen art. 9-data, wél verzwaarde governance).

## dbt-model `meta`

```yaml
meta:
  domain: ww
  legal_basis: WW_art_24_27
  purpose-limitation: [handhaving]
  bio_classificatie: vertrouwelijk
  retention period_jaren: 7
  eigenaar: divisie_ww
  pii_kolommen: [bsn]
  risk_tier: hoog
  human_in_the_loop: true
  algoritmeregister_id: ODAP-CLAIMS-ATTRIBUTION-001  # placeholder
```

## OPA-policies

- Access tot `gold.uc03_fraud_risk.*` alleen voor rol `fraud_analyst` met doelcode `handhaving`.
- Singular test (Rego): geen *protected attributes* (etniciteit, wijk-code) in features. Falt af bij detectie.
- Audit-log van **elke** read (volledig, niet samples): WW-handhaving is
  toezicht-gevoelig.

## OpenMetadata

- Tags: `Domain.WW`, `AI.Risk.Hoog`, `Purpose limitation.handhaving`, `Algoritmeregister.ODAP-CLAIMS-ATTRIBUTION-001`.
- Custom property `champion_challenger`: link naar A/B-experiment-id.
- Lineage: bronze → silver → mart → (latere: model-feature → score → behandeling → besluit).

## Outputs

- `dbt/models/staging/ww/{stg_service_request_application.sql, stg_ww_opzegging.sql, schema.yml}`
- `dbt/models/marts/uc03_fraud_risk/{mart_uc03_verwijtbaar_signalen.sql, schema.yml}`
- `dbt/tests/test_no_protected_attributes_uc03.sql` (singular test)

## TODO voor production-uitbreiding

- Drift detection (data + concept) met alerts.
- Champion-challenger setup met A/B-routing.
- Volledig auditspoor van model → score → behandeling → besluit.
- Algoritmeregister-publicatie.
