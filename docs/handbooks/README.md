# Handleidingen per rol

Dit is de gebruikersdocumentatie van het UWV Referentie Data- en Analyseplatform,
opgesplitst per rol. Elke rol heeft zijn eigen handleiding met:

1. **Inloggen, MFA & applicaties** — hoe je begint
2. **Welke data je wel en niet ziet** — catalogs, schemas, kolom-maskers, rij-filters
3. **Dagelijkse workflows met voorbeelden** — concrete scenario's, queries, dashboards
4. **Hulp, fouten & escalatie** — wat te doen bij problemen

> **Belangrijk.** Dit platform is een **fictieve, illustratieve referentie-implementatie**.
> Alle datasets zijn synthetisch (alleen 9-prefix BSN's, `meta.synthetic: true`).
> De handleidingen beschrijven hoe het platform *werkt*, niet hoe production werkt.
> Productie-installaties verwijzen naar dit document als blauwdruk, niet als procedure.

---

## Overzicht van rollen

Het platform onderscheidt **11 menselijke rollen** + **1 systeemrol**, gemodelleerd
in [`infrastructure/helm/keycloak/realm.json`](../../infrastructure/helm/keycloak/realm.json)
en [`opa-policies-src/data/role_mappings.json`](../../opa-policies-src/data/role_mappings.json).

### Business-rollen (eindgebruikers)

| # | Rol | Domein | Handleiding |
|---|---|---|---|
| 1 | Claims Analyst | AG / WIA | [01-claims-analyst.md](01-claims-analyst.md) |
| 2 | Fraud Analyst | WW | [02-fraud-analyst.md](02-fraud-analyst.md) |
| 3 | Claims Analyst | AG / Wajong | [03-claims-analyst.md](03-claims-analyst.md) |
| 4 | Marketing Analyst | CRM / Klantcontact | [04-marketing-analyst.md](04-marketing-analyst.md) |
| 5 | Finance Analyst | Financiën | [05-finance-analyst.md](05-finance-analyst.md) |
| 6 | Operations Manager | Sociaal-medische zaken | [06-operations-manager.md](06-operations-manager.md) |
| 7 | Marketing Analyst | Toeslagenwet (proactief) | [07-marketing-analyst.md](07-marketing-analyst.md) |
| 8 | Researcher | Onderzoek (sandbox) | [08-researcher.md](08-researcher.md) |

### Technische rollen (platform-team)

| # | Rol | Verantwoordelijkheid | Handleiding |
|---|---|---|---|
| 9 | Data-steward | Datakwaliteit, governance, lineage | [09-data-steward.md](09-data-steward.md) |
| 10 | Data-engineer | Pipelines, ingestion, transformaties | [10-data-engineer.md](10-data-engineer.md) |
| 11 | Platform-admin | Cluster, security, break-glass | [11-platform-admin.md](11-platform-admin.md) |

### Systeemrol

| # | Rol | Functie | Handleiding |
|---|---|---|---|
| 12 | Smoketest | Service-account voor automated tests + dbt-runs | [12-smoketest-systeem.md](12-smoketest-systeem.md) |

---

## Eén gebundeld handboek

Voor distributie of offline lezen is er een **gebundeld handboek** met alle
rollen achter elkaar:

- Markdown: [00-handboek.md](00-handboek.md)
- Word (.docx): `ODAP_Platform_Handbook_per_role.docx` in de hoofdmap

---

## Veelgebruikte begrippen

| Term | Uitleg |
|---|---|
| **Catalog** | Trino-namespace die overeenkomt met een datazone: `bronze`, `silver`, `gold`, `sensitive`, `sandbox`. |
| **Schema** | Domein binnen een catalog, bv. `silver.wia` of `gold.uc01_wia_funnel`. |
| **OPA** | Open Policy Agent — bepaalt bij elke query wie wat mag zien. |
| **Doelbinding** | De wettelijke taak waarvoor data verwerkt mag worden. Toegang vereist een geldig doel. |
| **PII** | Persoonlijk Identificeerbare Informatie (BSN, naam, geboortedatum, adres). |
| **Pseudonimisering** | Vervangen van BSN door een hash + zout — niet herleidbaar zonder sleutel. |
| **Sensitive Vault** | Aparte catalog voor bijzondere persoonsgegevens (art. 9 AVG). |
| **Mart** | Eindproduct van dbt: een tabel/view klaar voor consumptie in `gold.*`. |
| **JIT-toegang** | Just-in-time: tijdelijke verhoogde rechten met audit-log, alleen op aanvraag. |
| **Break-glass** | Noodprocedure: admin-toegang die altijd gelogd en achteraf gereviewd wordt. |

---

## Zes regels die voor iedereen gelden

1. **Doelbinding eerst** — gebruik data alleen voor de taak waarvoor je rol toegang heeft.
2. **Niets is "zomaar"** — elke query wordt gelogd, elke toegang is herleidbaar.
3. **Mens beslist** — algoritmes geven advies, jij neemt het besluit.
4. **Bij twijfel niet doen** — vraag eerst de data-steward of platform-admin.
5. **Geen schermafbeeldingen van persoonsgegevens** — ook niet voor bug-rapporten.
6. **Geen wachtwoorden delen** — ook niet "even snel" met collega's.

---

## Eerste hulp

Werkt iets niet? In deze volgorde:

1. **Lees** de sectie *Hulp, fouten & escalatie* in jouw rol-handleiding.
2. **Vraag** een collega met dezelfde rol.
3. **Mail** de data-steward (`data.steward@odap.local:8443`).
4. **Voor incidenten** (rare meldingen, plotse toegang verloren, vermoede inbreuk):
   bel de platform-admin direct, niet via e-mail.
