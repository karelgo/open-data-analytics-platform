# UC-10 — Mijn Gegevensdiensten 2.0 (modernisering ketenleveringen)

| Status in deze repo | **Spec + dbt-mart per afnemer** — geen API-gateway in fase 0–10 |
|---|---|
| Domein | Polisadministratie (cross-keten) |
| Risicoclassificatie | Hoog uit ketenoogpunt (lessons learned Suwinet AP-onderzoek 2014) |
| AVG-grondslag | Art. 6 lid 1c per afnemer; purpose-limitation strikt afgebakend |
| Retention period audit-logs | 7 jaar |

Bron: [`referentiearchitecture-odap-data-analytics.md` § 8 UC-10](../../referentiearchitecture-odap-data-analytics.md).

---

## Context

Suwinet-Inkijk en weekleveringen zijn verouderd. Ketenpartners (gemeenten,
IND, DUO, Belastingdienst, deurwaarders) verwachten moderne API's met
fijnmazige purpose-limitation. Lessons learned uit AP-onderzoek Suwinet (2014):
verwerkersovereenkomsten compleet, periodieke controle op afnemer-naleving.

## Doel

API-gateway voor real-time bevraging op CGM gold-data-products, met
**expliciete purpose-limitation per call** en backwards compatibility met SuwiML
voor partijen die nog niet over zijn.

## Data

| Data product | Inhoud | Afnemers (illustratief) |
|---|---|---|
| `gold.uc10_polisadm_dagloon` | Recente daglonen per BSN + periode | Gemeente WMO, IND, DUO |
| `gold.uc10_claim payout_status` | Lopend ja/nee + soort | Gemeente WMO, deurwaarders |
| `gold.uc10_doelgroepregister` | Banenafspraak indicatie | Werkgevers (eHerkenning) |

**CGM-entiteiten**: `Polisadministratie`, `Doelgroepregister`, `Claim payout`.

## Architecture-pad (in deze repo)

```
gold.uc05_customer_360 (intern) + silver.polisadm + silver.doelgroepregister
                       │
                       ▼
            mart_uc10_polisadm_dagloon.sql
            mart_uc10_claim payout_status.sql
            mart_uc10_doelgroepregister.sql
                       │
                       ▼
       Trino REST API (intern via OPA-policy "afnemer X mag UC-10-mart Y")
                       │
                       ▼
       [Out-of-scope deze repo]
       API-gateway met:
       - OAuth2 client credentials per afnemer
       - Doelcode in elke API-call (HTTP header X-Purpose)
       - Filter op selectiecriteria (regio, leeftijd) in OPA
       - Volledige audit-log naar SOC + naar afnemende partij
       - Backwards compatibility met SuwiML/XML
```

## OPA-policies (kritiek)

`opa-policies-src/trino/trino-uc10-afnemers.rego` (in fase 9):

- Per afnemer een **client-id** in JWT.
- Per afnemer een **toegestane doelcode-set** (`["WMO", "Inning"]` voor
  gemeente; `["Naturalisatie"]` voor IND).
- Per afnemer een **mart-accesss-set** (welke `uc10_*`-tabellen).
- Header `X-Purpose` moet matchen met afnemer's toegestane set, **én**
  with the purpose-limitation-tag van de mart, **anders deny + audit-log**.
- Logging van afnemer + doelcode + bevraagde BSN (geen response in log).

## dbt-model `meta`

```yaml
meta:
  domain: polisadm
  legal_basis: Wet_SUWI+Wfsv
  purpose-limitation: [externe_levering]
  bio_classificatie: vertrouwelijk
  retention period_jaren: 7
  eigenaar: data_office
  pii_kolommen: [bsn, lh_nummer]
  risk_tier: hoog_keten
  audit_log_required: true
  afnemer_doelcode_required: true
```

## OpenMetadata

- Tags: `Domain.Polisadm`, `LegalBasis.Wet_SUWI`, `Purpose limitation.externe_levering`,
  `Audit.LogPerCall.true`.
- Custom property `afnemer_contracten`: link naar verwerkersovereenkomsten
  (placeholder).
- Per UC-10-mart een aparte glossary-entry "Gegevensdienst <name>".

## Outputs (reference implementation)

- `dbt/models/marts/uc10_gegevensdiensten/{mart_uc10_polisadm_dagloon.sql, mart_uc10_claim payout_status.sql, mart_uc10_doelgroepregister.sql, schema.yml}`.
- `opa-policies-src/trino/trino-uc10-afnemers.rego` (skeleton in fase 9).
- `opa-policies-src/data/consumer_purpose_codes.json` (mock-mappings).

## Open vragen / TODO

- Echte API-gateway-implementatie (Kong/APISIX/Trino HTTP-passthrough) —
  out-of-scope referentie. Alleen Trino REST + OPA als minimale variant.
- SuwiML/XML adapter — out-of-scope.
- Periodieke afnemer-naleving-controle — out-of-scope (organisatorisch).

## Compliance koppeling

- R-NORA-02 (open API's): adresseert deze UC primair.
- R-AVG-06 (purpose-limitation): kritiek — geïmplementeerd via OPA.
- R-BIO-20 (logging): elke API-call gelogd, 7 jaar retentie.
- Lessons learned Suwinet-AP-onderzoek 2014: doelcode-per-call is **non-
  negotiable**.
