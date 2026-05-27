---
title: Identity & autorisatie
description: Hoe Keycloak en OPA samen bepalen wie wat mag zien.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Changes handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Identity & autorisatie

Access is geen kwestie van losse user-accounts per service — alle components
delegeren authenticatie naar **Keycloak** (OIDC) en autorisatie op queries
naar **Open Policy Agent (OPA)**.

## Auth-flow

```mermaid
sequenceDiagram
    participant U as Gebruiker (browser)
    participant K as Keycloak
    participant T as Trino
    participant O as OPA
    participant D as Data (MinIO via Hive)

    U->>K: GET /auth?client_id=trino
    K-->>U: redirect met code
    U->>T: GET /ui?code=…
    T->>K: token exchange
    K-->>T: id_token + role claims
    U->>T: SQL query
    T->>O: input { token, query, table, columns }
    O-->>T: allow + row_filter + column_masks
    T->>D: pushdown query (gefilterd + gemaskeerd)
    D-->>T: gefilterde rijen
    T-->>U: resultaten
```

## Identity provider — Keycloak

- **Realm:** `uwv` in [`infrastructure/helm/keycloak/realm.json`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/infrastructure/helm/keycloak/realm.json)
- **Mock-rollen** in deze referentie:
    - Business: `claims_analyst`, `fraud_analyst`, `claims_analyst`,
      `marketing_analyst`, `finance_analyst`, `operations_manager`, `marketing_analyst`,
      `researcher`
    - Tech: `data_steward`, `data_engineer`, `platform_admin`
- **MFA:** TOTP verplicht voor tech-rollen; aanbevolen voor business-rollen
  (configureerbaar in realm-export).
- **Token-claim** `groups` bevat de Keycloak-groepen → mapt naar OPA-rollen.

Elk component (Trino, Superset, Airflow, NiFi, OpenMetadata) configureert
Keycloak via een Stackable `AuthenticationClass` — zie
[`platform/02-authentication/`](https://github.com/fresh-minds/FreshStackableDataPlatform/tree/main/platform/02-authentication).

## Authorisatie — OPA + Rego

Trino delegeert elke query naar OPA via het `opa-authorizer`-plugin:

```
Trino-query ──► OPA bundle (uit ConfigMap) ──► allow/deny + row filters + column masks
```

De Rego-policies in [`opa-policies-src/`](https://github.com/fresh-minds/FreshStackableDataPlatform/tree/main/opa-policies-src):

| Policy | Doel |
|---|---|
| `trino-base.rego` | OIDC token-validatie, role-mapping |
| `trino-data-access.rego` | Catalog/schema/table-access per rol |
| `trino-purpose-limitation.rego` | Purpose limitation (purpose) afdwingen op gold-tabellen |
| `trino-row-filters.rego` | Rij-filters per rol (bijv. Fraud Analyst ziet alleen WW-claims) |
| `trino-column-masks.rego` | Kolom-maskering (PII, gezondheid → hash of `***`) |
| `trino-platform-roles.rego` | UWV-rol-definities (single source) |

Build van de bundle: `scripts/build-opa-bundle.sh`, geïntegreerd in
`make deploy-platform`.

!!! tip "Purpose limitation eerst"
    Bij elke query controleert OPA of er een **geldig doel** is meegegeven
    (bijv. `claim payout`, `handhaving`, `onderzoek`). Zonder doel: deny.
    Purpose limitation is harder dan rol — een Claims Analyst zonder doel
    `claim payout` krijgt ook in zijn eigen mart geen data.

## Zie ook

- [ADR-0003 · OPA als Trino-authz](../adr/0003-opa-as-trino-authz.md)
- [ADR-0008 · Self-service data-access](../adr/0008-self-service-data-access.md)
- [Access request (handbook)](../access-request-guide.md)
- [Compliance-mapping § AVG](../compliance-mapping.md)
