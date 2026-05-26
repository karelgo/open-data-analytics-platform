---
title: Rollen — overzicht
description: Welke rollen het platform onderscheidt en wie wat ziet.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Wijzigingen handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Rollen op het platform

Het platform onderscheidt **11 menselijke rollen** + **1 systeemrol**,
gemodelleerd in [`infrastructure/helm/keycloak/realm.json`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/infrastructure/helm/keycloak/realm.json)
en [`opa-policies-src/data/role_mappings.json`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/opa-policies-src/data/role_mappings.json).

## Business-rollen (eindgebruikers)

| # | Rol | Domein | Handleiding |
|---|---|---|---|
| 1 | Claims Analyst | AG / WIA | [01-claims-analyst](../handbooks/01-claims-analyst.md) |
| 2 | Fraud Analyst | WW | [02-fraud-analyst](../handbooks/02-fraud-analyst.md) |
| 3 | Claims Analyst | AG / Wajong | [03-claims-analyst](../handbooks/03-claims-analyst.md) |
| 4 | Marketing Analyst | CRM / Klantcontact | [04-marketing-analyst](../handbooks/04-marketing-analyst.md) |
| 5 | Finance Analyst | Financiën | [05-finance-analyst](../handbooks/05-finance-analyst.md) |
| 6 | Operations Manager | Sociaal-medische zaken | [06-operations-manager](../handbooks/06-operations-manager.md) |
| 7 | Marketing Analyst | Toeslagenwet (proactief) | [07-marketing-analyst](../handbooks/07-marketing-analyst.md) |
| 8 | Researcher | Onderzoek (sandbox) | [08-researcher](../handbooks/08-researcher.md) |

## Technische rollen (platform-team)

| # | Rol | Verantwoordelijkheid | Handleiding |
|---|---|---|---|
| 9 | Data-steward | Datakwaliteit, governance, lineage | [09-data-steward](../handbooks/09-data-steward.md) |
| 10 | Data-engineer | Pipelines, ingestion, transformaties | [10-data-engineer](../handbooks/10-data-engineer.md) |
| 11 | Platform-admin | Cluster, security, break-glass | [11-platform-admin](../handbooks/11-platform-admin.md) |

## Systeemrol

| # | Rol | Functie | Handleiding |
|---|---|---|---|
| 12 | Smoketest | Service-account voor automated tests + dbt-runs | [12-smoketest-systeem](../handbooks/12-smoketest-systeem.md) |

## Zes regels die voor iedereen gelden

1. **Doelbinding eerst** — gebruik data alleen voor de taak waarvoor je rol toegang heeft.
2. **Niets is "zomaar"** — elke query wordt gelogd, elke toegang is herleidbaar.
3. **Mens beslist** — algoritmes geven advies, jij neemt het besluit.
4. **Bij twijfel niet doen** — vraag eerst de data-steward of platform-admin.
5. **Geen schermafbeeldingen van persoonsgegevens** — ook niet voor bug-rapporten.
6. **Geen wachtwoorden delen** — ook niet "even snel" met collega's.

## Welke rol ziet welk component?

| Rol | keycloak | nifi | kafka | minio | hive | spark | trino | opa | superset | openmetadata | dbt-docs | jupyter | airflow | prometheus | grafana | opensearch | multica | powerbi | nanitics |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `claims_analyst` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `fraud_analyst` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `claims_analyst` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `marketing_analyst` | ✓ |  |  |  |  |  |  |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `finance_analyst` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `operations_manager` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `marketing_analyst` | ✓ |  |  |  |  |  | ✓ |  | ✓ |  |  |  |  |  |  |  |  | ✓ |  |
| `researcher` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `data_steward` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |  | ✓ |  |
| `data_engineer` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ | ✓ | ✓ | ✓ |  | ✓ |  | ✓ |  | ✓ |
| `platform_admin` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `data_analyst` | ✓ |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | ✓ |  |

Een ✓ in `keycloak` betekent dat alle rollen erover SSO'en. Voor `multica`,
`prometheus`, en sommige observability-componenten beperken we toegang
expliciet tot platform-rollen.
