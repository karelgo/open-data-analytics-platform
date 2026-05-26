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
| 1 | WIA-beoordelaar | AG / WIA | [01-wia-beoordelaar](../handleidingen/01-wia-beoordelaar.md) |
| 2 | WW-handhaver | WW | [02-ww-handhaver](../handleidingen/02-ww-handhaver.md) |
| 3 | Wajong-arbeidsdeskundige | AG / Wajong | [03-wajong-arbeidsdeskundige](../handleidingen/03-wajong-arbeidsdeskundige.md) |
| 4 | CRM-medewerker | CRM / Klantcontact | [04-crm-medewerker](../handleidingen/04-crm-medewerker.md) |
| 5 | FEZ-analist | Financiën | [05-fez-analist](../handleidingen/05-fez-analist.md) |
| 6 | SMZ-planner | Sociaal-medische zaken | [06-smz-planner](../handleidingen/06-smz-planner.md) |
| 7 | Proactief dienstverlener | Toeslagenwet (proactief) | [07-proactief-dienstverlener](../handleidingen/07-proactief-dienstverlener.md) |
| 8 | Researcher | Onderzoek (sandbox) | [08-researcher](../handleidingen/08-researcher.md) |

## Technische rollen (platform-team)

| # | Rol | Verantwoordelijkheid | Handleiding |
|---|---|---|---|
| 9 | Data-steward | Datakwaliteit, governance, lineage | [09-data-steward](../handleidingen/09-data-steward.md) |
| 10 | Data-engineer | Pipelines, ingestion, transformaties | [10-data-engineer](../handleidingen/10-data-engineer.md) |
| 11 | Platform-admin | Cluster, security, break-glass | [11-platform-admin](../handleidingen/11-platform-admin.md) |

## Systeemrol

| # | Rol | Functie | Handleiding |
|---|---|---|---|
| 12 | Smoketest | Service-account voor automated tests + dbt-runs | [12-smoketest-systeem](../handleidingen/12-smoketest-systeem.md) |

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
| `wia_beoordelaar` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `ww_handhaver` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `wajong_arbeidsdeskundige` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `crm_medewerker` | ✓ |  |  |  |  |  |  |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `fez_analist` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `smz_planner` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `proactief_dienstverlener` | ✓ |  |  |  |  |  | ✓ |  | ✓ |  |  |  |  |  |  |  |  | ✓ |  |
| `researcher` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `data_steward` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |  | ✓ |  |
| `data_engineer` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ | ✓ | ✓ | ✓ |  | ✓ |  | ✓ |  | ✓ |
| `platform_admin` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `data_analyst` | ✓ |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | ✓ |  |

Een ✓ in `keycloak` betekent dat alle rollen erover SSO'en. Voor `multica`,
`prometheus`, en sommige observability-componenten beperken we toegang
expliciet tot platform-rollen.
