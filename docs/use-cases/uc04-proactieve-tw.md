# UC-04 — Proactieve TW-aanvulling (Wet proactieve dienstverlening SZW)

| Status in deze repo | **Volledig geïmplementeerd** in dbt-mart |
|---|---|
| Domein | WW + WIA + Wajong + TW |
| Risicoclassificatie | Laag (geen profilering, regel-gebaseerd) |
| AVG-grondslag | Art. 6 lid 1e (Wet proactieve dienstverlening SZW, 2025) |
| Bewaartermijn | 7 jaar |

Bron: [`referentiearchitectuur-odap-data-analytics.md` § 8 UC-04](../../referentiearchitectuur-odap-data-analytics.md).

---

## Probleem

Cliënten met een lage uitkering hebben mogelijk recht op TW-aanvulling, maar
hebben geen aanvraag gedaan. De Wet proactieve dienstverlening SZW (2025)
geeft grondslag om hen actief te wijzen op hun recht.

## Doel

Detecteer cliënten die **mogelijk recht** hebben op TW maar geen aanvulling
ontvangen, en lever een werklijst voor proactieve cliëntcommunicatie.

**Geen scoring of profilering** — uitsluitend regel-gebaseerde toets met
expliciete drempelwaarden.

## Data

| Bron | Inhoud |
|---|---|
| WW/WIA/Wajong-uitkering | Uitkering-type, hoogte, periode |
| Polisadministratie | Loon, dienstverband |
| BRP-spiegel | Huishoudsamenstelling, partner-aanwezigheid |
| Partnerinkomen (waar bekend) | Loonstrook partner via polisadm |

**CGM-entiteiten**: `Uitkering`, `Inkomen`, `Huishouden`.

## Architectuur-pad

```
silver.uitkeringen + silver.polisadm + silver.brp_spiegel + silver.partner_inkomen
                                     │
                                     ▼
                       mart_uc04_tw_eligibility.sql (Trino-side regel-toets)
                                     │
                                     ▼
                gold.uc04_tw_eligibility.lijst_potentieel_rechthebbend (incl. uitleg per regel)
                                     │
                                     ▼
                Werkmap-channel via cliëntcommunicatie-team (out-of-scope)
```

## Regel-toets (illustratief, vereenvoudigd)

```sql
-- Cliënt komt in lijst als:
--   1. Lopende WW/WIA/Wajong-uitkering, en
--   2. Uitkering ligt onder TW-norm voor diens huishoudsituatie, en
--   3. Geen lopende TW-aanvulling, en
--   4. Geen actieve opt-out
--
-- Drempelwaarden komen uit `dbt/seeds/tw_normen_<jaar>.csv` (CGM-conform).
```

## dbt-model `meta`

```yaml
meta:
  domain: ww   # cross-domein, primaire owner WW
  legal_basis: Wet_proactieve_dienstverlening_SZW_2025
  doelbinding: [proactieve_dienstverlening]
  bio_classificatie: vertrouwelijk
  bewaartermijn_jaren: 7
  eigenaar: divisie_ww   # met afstemming AG, AKO
  pii_kolommen: [bsn]
  risk_tier: laag
  profilering: false      # expliciet geen profilering
  opt_out_supported: true
  dpia_id: DPIA-UC04-2026-Q2  # placeholder
```

## OPA-policies

- Toegang tot `gold.uc04_tw_eligibility.*` alleen voor rol `marketing_analyst`
  + doelcode `proactieve_dienstverlening`.
- Audit-log per uitlezing (welke cliënten zijn benaderd) — gekoppeld aan
  `gold.uc04_tw_eligibility.benaderd_log` (door cliëntcommunicatie-team
  bijgehouden).
- Opt-out cliënten worden via row filter weggehouden uit gold (`opt_out = false`).

## OpenMetadata

- Tags: `Domain.WW`, `Wet.TW`, `LegalBasis.Wet_proactieve_dienstverlening_SZW`,
  `Doelbinding.proactieve_dienstverlening`, `Profilering.geen`.

## Outputs

- `dbt/seeds/tw_normen_2026.csv` (synthetische, op TW-norm-modelpatroon).
- `dbt/models/intermediate/{int_huishouden_inkomen.sql}`.
- `dbt/models/marts/uc04_tw_eligibility/{mart_uc04_tw_eligibility.sql, schema.yml}`.
- Compliance: DPIA-template-link (placeholder).

## Open vragen / TODO

- Werkelijke TW-norm-tabellen valideren met SZW (out-of-scope referentie).
- Werkmap-bericht-template ontwerpen (out-of-scope, organisatorisch).
