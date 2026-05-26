---
title: "Handleiding — Wajong-arbeidsdeskundige"
role: wajong_arbeidsdeskundige
---

> Rol-key: `wajong_arbeidsdeskundige` · Domein: AG / Wajong · Risiconiveau toegang: zeer hoog (Sensitive Vault, art. 9 AVG)

Deze handleiding is voor **arbeidsdeskundigen die Wajong-trajecten begeleiden**.
Jouw rol is bijzonder: je hebt als enige business-rol toegang tot de
**Sensitive Vault** met sociaal-medische gegevens. Voor sommige acties geldt
een **vier-ogen-principe**.

---

## 1. Wat doet jouw rol?

Je beoordeelt re-integratiekansen voor Wajongers en stelt trajecten op
(IPS, proefplaatsing, scholing). Je gebruikt het platform om:

- Wajong-dossiers te raadplegen (incl. medische gegevens)
- Beslissingsondersteunend advies uit UC-02 te zien (placeholder in deze referentie)
- Trajecten en uitkomsten te volgen
- Geanonimiseerde teamoverzichten te genereren

**Belangrijk.** Het UC-02 AI-model is in deze referentie een **placeholder**
(zie [docs/use-cases/uc02-wajong-ai.md](../use-cases/uc02-wajong-ai.md)). Een
echt werkend hoog-risico AI-systeem voor Wajong vereist DPIA, IAMA, bias-toets,
model-card, EU-registratie en externe audit. Dat is geen referentie-werk.

---

## 2. Inloggen, MFA & applicaties

### 2.1 Account

Accountnaam `wajong.arbeidsdeskundige`. **MFA verplicht** + extra waarschuwing
in de Keycloak-login: "Je hebt toegang tot de Sensitive Vault. Elke query wordt
gelogd en periodiek gereviewd."

### 2.2 Welke applicaties?

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Dashboards: caseload, trajecten | https://superset.odap.local |
| **OpenMetadata** | Begrippen, glossary, lineage | https://openmetadata.odap.local |

### 2.3 Vier-ogen-principe

Voor toegang tot `sensitive.wajong.*` geldt: **bepaalde queries vereisen een
co-signer**. In de huidige referentie wordt dit gemodelleerd door:

- Audit-log met automatische dagelijkse review door data-steward
- Voor productie: workflow-tool waarin een collega de aanvraag goedkeurt vóór de query

In deze referentie kun je alle sensitive-queries draaien, maar weet:
**elke sensitive-query verschijnt op het reviewscherm van de data-steward**
de volgende ochtend.

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs en schemas

| Catalog | Schema | Inhoud | Toegang |
|---|---|---|---|
| `silver` | `wajong` | Geconformeerd Wajong-dossier (gepseudonimiseerd waar mogelijk) | **Ja** |
| `gold` | `uc02_wajong` | Adviezen (placeholder mart) | **Ja** |
| `sensitive` | `wajong` | Sociaal-medisch dossier, diagnoses (art. 9 AVG) | **Ja** (4-eyes) |
| `silver` | `wia`, `ww`, `crm` | Andere domeinen | **Nee** |

### 3.2 Welke kolommen?

| Kolom | Wat zie je? |
|---|---|
| `bsn`, naam, geboortedatum, adres | Volledig — doel "reintegratie/behandeling" |
| `diagnose`, `icd10` | **Volledig** — uniek aan jouw rol (samen met platform-admin) |
| `iban`, `bankrekening` | Gemaskeerd — geen financieel doel |
| `regio` | Geen regio-filter — Wajong-traject mag landelijk |

### 3.3 Pseudonimisering — wanneer wel en niet?

In `silver.wajong.dossier_pseudonymised` is de BSN vervangen door een
pseudoniem (`bsn_pseudo`). Voor analyse over trajecten heen werk je vaak
op de gepseudonimiseerde tabel. Alleen bij dossier-specifiek werk
(de-anonimiseren voor één cliënt) gebruik je `sensitive.wajong.*`.

> **Vuistregel:** wat kan op `silver`, doe je op `silver`. Sensitive Vault is
> de uitzondering, niet de regel.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Caseload voor jouw team

```sql
SELECT
  trajectsoort,
  COUNT(*)         AS lopend,
  AVG(duur_dagen)  AS gem_duur
FROM gold.uc02_wajong.trajecten_actueel
WHERE arbeidsdeskundige_team = 'team-noord'
GROUP BY trajectsoort
ORDER BY lopend DESC;
```

### 4.2 Workflow B — Eén dossier ophalen (sensitive-query)

**Scenario.** Cliënt komt langs voor evaluatie van haar IPS-traject. Je
hebt het dossier nodig.

> **Let op.** Deze query raakt `sensitive.*`. Je doel ("behandeling") wordt
> meegegeven. De query verschijnt op het reviewscherm van de data-steward.

```sql
SELECT
  bsn,
  voornaam,
  achternaam,
  geboortedatum,
  diagnose,
  icd10,
  beoordeling_datum,
  participatieplan
FROM sensitive.wajong.dossier
WHERE bsn = '999000789';
```

In **DBeaver** of **Superset SQL Lab** voer je dit uit; je krijgt 1 rij terug.

### 4.3 Workflow C — Geanonimiseerde uitkomstanalyse

**Scenario.** "Werkt IPS beter dan proefplaatsing voor diagnose-categorie X?"

```sql
SELECT
  trajectsoort,
  diagnose_categorie,
  COUNT(*)                                                   AS aantal,
  AVG(CASE WHEN werkhervatting_6mnd THEN 1.0 ELSE 0.0 END)   AS slaag_pct
FROM gold.uc02_wajong.trajecten_uitkomst
WHERE start_jaar IN (2024, 2025)
GROUP BY trajectsoort, diagnose_categorie
HAVING COUNT(*) >= 30           -- privacy: geen kleine groepen
ORDER BY trajectsoort, diagnose_categorie;
```

> **Privacy-regel.** Aggregaten met < 30 records onderdrukt het platform niet
> automatisch. Pas zelf de `HAVING COUNT(*) >= N`-grens toe om herleidbaarheid
> te voorkomen. Bij twijfel: data-steward.

### 4.4 Workflow D — Adviezen uit UC-02 raadplegen (placeholder)

```sql
SELECT
  bsn_pseudo,
  advies_traject,
  score,
  top_drivers          -- SHAP-achtige verklaring
FROM gold.uc02_wajong.advies_placeholder
WHERE advies_datum = CURRENT_DATE
ORDER BY score DESC
LIMIT 50;
```

> **Mens beslist.** Het advies is een hulpmiddel. **Jij** bepaalt het traject.
> De top_drivers maken transparant op welke factoren het advies steunt.

### 4.5 Workflow E — Lineage verifiëren

**Scenario.** Een cliënt vraagt "Welke gegevens gebruiken jullie over mij?"

1. Open OpenMetadata → zoek `sensitive.wajong.dossier`
2. Klik **Lineage** — zie alle bronnen die naar dit dossier leiden
3. Klik elke bron aan → zie eigenaar, classificatie, doelbinding
4. Antwoord de cliënt op basis van wat je daar ziet (gestructureerd, niet uit het hoofd)

---

## 5. Hulp, fouten & escalatie

### 5.1 Foutmeldingen

| Foutmelding | Betekenis | Actie |
|---|---|---|
| `Access Denied: column 'iban' is masked` | IBAN niet voor jouw doel | Doorgaan, niet nodig voor reintegratie |
| `Access Denied: silver.wia.*` | WIA-domein niet toegankelijk | Vraag WIA-beoordelaar |
| `Audit-flag: review required` | Sensitive-query staat klaar voor review | Niets doen — review verloopt automatisch |
| `Authentication failed: token expired` | Sessie verlopen | Opnieuw inloggen via Keycloak |

### 5.2 Datalek-vermoeden

Als je per ongeluk gegevens ziet die niet bedoeld zijn voor jouw doel,
of als je een incident opmerkt:

1. **Niet verder kijken.** Sluit het scherm.
2. **Bel** platform-admin direct (binnen werktijd) of de Platform CISO (buiten werktijd).
3. **Schrijf** een notitie binnen 24 uur (datum, tijd, query, omschrijving).

Dit valt onder de **NIS2-meldplicht 24 uur vroegsignalering**.

### 5.3 Wie helpt?

| Probleem | Contact |
|---|---|
| Inloggen / MFA | Platform-admin |
| Vraag over diagnose-codes | Data-steward → glossary in OpenMetadata |
| "Ik twijfel of ik dit mag zien" | Data-steward — vraag het vóór je het doet |
| Vermoeden van inbreuk | Platform-admin telefonisch + Platform CISO |

---

## 6. Wat je nooit doet

- Een dossier bekijken zonder concrete cliënt-aanleiding.
- Sensitive-queries draaien voor onderzoek (gebruik `silver.*` of pseudonymized).
- Diagnoses delen via mail of chat.
- Print-screens van medische velden maken — ook niet voor casuïstiek-bespreking.
- Dossier-resultaten exporteren naar Excel zonder pseudonimisering.

---

## 7. Verantwoordelijkheid (kort)

Je rol staat onder **doelbinding "reintegratie" / "behandeling"** met
AVG-grondslag art. 6 lid 1e + art. 9 lid 2h (gezondheid, sociale zekerheid).
Vier-ogen-principe geldt voor sensitive-queries in productie. Bewaartermijn
voor besluitvormingsdata: 7 jaar.

---

**Vorige:** [02-ww-handhaver.md](02-ww-handhaver.md) ·
**Volgende:** [04-crm-medewerker.md](04-crm-medewerker.md) ·
**Index:** [README.md](README.md)
