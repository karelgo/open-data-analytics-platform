# UC-02 — Wajong reintegration-kansen (hoog-risico AI)

| Status in deze repo | **Placeholder** — geen werkende ML-pipeline |
|---|---|
| Domein | AG (Wajong) |
| Risicoclassificatie | **Hoog (AI Act, Annex III)** |
| AVG-grondslag | Art. 6 lid 1e (wettelijke taak) **+ art. 9 lid 2h** (gezondheid, sociale zekerheid) |
| Retention period | 7 jaar besluitvormingsdata; trainingsset apart, onder eigen retentie |

Bron: [`referentiearchitecture-odap-data-analytics.md` § 8 UC-02](../../referentiearchitecture-odap-data-analytics.md).

> **Belangrijk.** Op verzoek van de opdrachtgever wordt UC-02 in deze referentie
> niet als werkend ML-systeem geïmplementeerd. Reden: een echt hoog-risico
> AI-systeem voor Wajong vereist **DPIA + IAMA + bias-toetsing + model card +
> EU-registratie + externe audit**. Dat is geen referentie-werk maar een
> volledig MLOps-traject onder UWV's MRM-beleid.
>
> Wat er wél staat: een **complete spec**, een **placeholder-mart** met
> `meta.risk_tier: hoog` en `meta.dpia_required: true`, en **TODO's** die
> for a echte implementatie afgevinkt moeten worden.

---

## Probleem

Research "Wat werkt bij Wajongers" toonde dat naast harde dossierkenmerken
ook zachte factoren (motivatie, omgeving) voorspellend zijn. UWV-arbeids-
deskundigen hebben behoefte aan beslissingsondersteuning bij keuze van
reintegrationtraject (IPS, proefplaatsing, scholing).

## Doel

Decision support: per cliënt schatting van kans op duurzaam werk (≥ 6 maanden)
bij verschillende interventies. **Geen automatisch besluit** — model
adviseert, arbeidsdeskundige beslist.

## Data

| Bron | Inhoud | Klassificatie |
|---|---|---|
| Wajong-dossier | Assessment, participatieplan | Vertrouwelijk |
| Operational dossier | Diagnose, beperkingen | **Bijzonder PG art. 9** |
| Eerdere trajecten | Uitkomst (werk ja/nee, duur) | Vertrouwelijk |
| Polisadministratie | Werkhistorie, dagloon | Vertrouwelijk |
| Scholingsbudget-data | Toegekende scholing | Intern |

**CGM-entiteiten**: `Cliënt`, `Diagnose`, `Traject`, `Werkhervatting`.

## Architecture-pad (placeholder)

```
[BRONZE]    sensitive.eligibility_cases.dossier (Sensitive Vault, art. 9)
            silver.eligibility_cases.case_pseudonymised (re-id alleen via sensitive-vault)
                  │
                  ▼
[FEATURES]  sensitive.eligibility_cases.features_v1  (in Sensitive Vault)
                  │
                  ▼
[MODEL]     SparkApplication training (TODO)
            Algorithm: XGBoost (placeholder)
            Output: model-artefact in s3://odap-meta/models/uc02_complex_cases_v1/
                  │
                  ▼
[INFERENCE] Spark batch inference → gold.uc02_complex_cases.advies (per cliënt: top-3 trajecten + score + SHAP-driver)
                  │
                  ▼
[UI]        Arbeidsdeskundige-dossiersysteem (out-of-scope deze repo)
```

## dbt-model `meta` (placeholder mart)

```yaml
# dbt/models/marts/uc02_complex_cases/mart_uc02_advies_placeholder.sql
meta:
  domain: ag
  subdomain: wajong
  legal_basis: WIA_art_64+art_9_2h
  purpose-limitation: [reintegration]
  bio_classificatie: vertrouwelijk
  pii_kolommen: [bsn_pseudo]   # geen ruwe BSN; alleen pseudoniem
  retention period_jaren: 7
  eigenaar: divisie_ag
  risk_tier: hoog              # AI Act Annex III
  dpia_required: true
  iama_required: true
  human_in_the_loop: true
  status: placeholder
  todo:
    - Voer DPIA uit en koppel referentie hier
    - Voer IAMA uit en koppel referentie hier
    - Bias-toetsing op leeftijd, geslacht, herkomst, regio
    - Model card publiceren
    - EU-registratie hoog-risico AI (deadline aug 2026)
    - Externe audit jaarlijks
    - Drift monitoring met alerts
    - Champion-challenger setup
    - Mens-in-de-lus workflow gevalideerd door arbeidsdeskundige
```

## OPA-policies

- `sensitive.eligibility_cases.*` is **default-deny** voor alle rollen behalve
  `claims_analyst` met expliciete doelcode `reintegration`.
- 4-eyes principe op `sensitive.eligibility_cases.dossier`: query met
  `bsn_pseudo IS NOT NULL` vereist dual-approval (Rego-policy controleert
  `request_context.dual_approval_token`).
- Logging van elke read; OpenSearch retention 7 jaar.

## OpenMetadata

- Tags: `Domain.AG`, `Wet.Wajong`, `Health.Article9`, `AI.Risk.Hoog`,
  `LegalBasis.WIA_art_64+art_9_2h`.
- Custom property `algoritmeregister_id`: link naar algoritmeregister.uwv.nl
  (placeholder).
- Glossary-koppelingen: `Cliënt`, `Diagnose`, `Traject`, `Werkhervatting`.

## Compliance-checklist (afgevinkt voor placeholder)

- [x] Spec gedocumenteerd (dit bestand)
- [x] Mart-skelet met `meta.risk_tier=hoog`, `dpia_required=true`
- [x] Sensitive Vault catalog ontworpen (`sensitive.*`)
- [x] OPA default-deny op `sensitive.eligibility_cases.*` (zal in fase 9 geactiveerd worden)
- [ ] DPIA uitgevoerd (TODO — niet in deze repo)
- [ ] IAMA uitgevoerd (TODO)
- [ ] Bias-toetsing rapport (TODO)
- [ ] Model card (TODO)
- [ ] EU-registratie hoog-risico AI (TODO)
- [ ] Externe audit (TODO)

## Outputs (artefacten in repo)

- Dit document.
- `dbt/models/marts/uc02_complex_cases/mart_uc02_advies_placeholder.sql` (alleen `meta`, geen SELECT van echte data).
- `platform/09-trino/catalogs/catalog-sensitive.yaml.tmpl` — Sensitive Vault catalog template (gebruikt door alle UC's met art. 9-data).

## Open vragen

- Volgens AI Act-deadline aug 2026 vereist een production-versie EU-registratie.
  Voor de referentie volstaat `algoritmeregister_id: TBD`.
