# Handleiding — Marketing Analyst

> Rol-key: `marketing_analyst` · Domein: Klantcontact · Risiconiveau toegang: middel (PII gemaskeerd, geen medisch)

Deze handleiding is voor **medewerkers van klantcontact en CRM**. Je werkt
met het 360°-cliëntbeeld (UC-05) en helpt cliënten via telefoon, balie of
Werkmap. Je ziet **gemaskeerde BSN's** en **geen medische gegevens** —
beide bewust beperkt om dataminimalisatie te respecteren.

---

--8<-- "_snippets/url-modes.md"

## 1. Wat doet jouw rol?

Je beantwoordt vragen van cliënten en routeert hen naar de juiste afdeling.
Je gebruikt het platform om:

- Het 360°-cliëntbeeld te raadplegen (UC-05)
- Te zien welke uitkeringen lopen, welke klantcontacten al hebben plaatsgevonden
- Trends in klantvraag te zien per kanaal
- Geen besluiten te nemen over uitkering of behandeling — dat doen domein-rollen

---

## 2. Inloggen, MFA & applicaties

### 2.1 Account

Accountnaam `marketing.analyst`. **MFA verplicht**. Bij eerste login
wachtwoord wijzigen.

### 2.2 Welke applicaties?

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Cliënt-360-dashboard, contact-trends | https://superset.odap.local:8443 |
| **OpenMetadata** | Begrippen opzoeken | https://openmetadata.odap.local:8443 |

Voor productie: meestal werk je vanuit een **Werkmap-frontend** die UC-05
via Trino REST API consumeert. Het platform is dan onzichtbaar; deze
referentie laat zien wat erachter zit.

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalog en schema

| Catalog | Schema | Inhoud | Toegang |
|---|---|---|---|
| `gold` | `uc05_customer_360` | 360°-cliëntbeeld | **Ja** |
| `silver` | `crm` | Klantcontact-historie | **Indirect** (alleen via UC-05) |
| `silver` | `wia`, `ww`, `wajong` | Domein-data | **Nee** |
| `sensitive` | * | (geen) | **Nee** |

### 3.2 Welke kolommen?

In `gold.uc05_customer_360.client_overview`:

| Kolom | Wat zie je? |
|---|---|
| `bsn` | **GEMASKEERD** — `'XXXXXXX' || substring(bsn, 8)` (laatste 2 cijfers zichtbaar) |
| `voornaam`, `achternaam` | Volledig — voor herkenning aan de telefoon |
| `birth_date` | Volledig — voor identificatie |
| `straat`, `huisnummer` | Volledig — adres voor balie |
| `iban`, `bankrekening` | **GEMASKEERD** — niet nodig voor klantcontact |
| `diagnose`, `icd10` | NULL (kolom-mask) — geen medisch |
| `lopende_uitkeringen` | Type + status + bedrag-categorie | Voor doorverwijzing |
| `kanaal_voorkeur` | Telefoon / Werkmap / Brief | Voor klantcontact |
| `opt_out` | Ja/nee proactieve dienstverlening | Respecteer altijd |

### 3.3 Doelbinding

Je rol heeft de purposes **"klantcontact"** en **"behandeling"**. Een query
die data uit een andere zone aanspreekt zonder geldig doel wordt geweigerd.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Cliënt aan de telefoon

**Scenario.** Mevrouw Jansen belt: "Ik krijg geen brief, maar wel een
betaling. Klopt dat?"

1. Vraag haar birth_date + de laatste 2 cijfers van haar BSN voor identificatie.
2. Open **Superset → dashboard "Cliënt 360°"**, zoek op gemaskeerde BSN of birth_date + naam.
3. Bekijk de tegels: Lopende uitkering, Laatste contact, Kanaalvoorkeur.
4. Beantwoord de vraag of route je haar naar de juiste afdeling.

### 4.2 Workflow B — Trends in kanaalkeuze

**Scenario.** Hoeveel cliënten zijn de afgelopen maand overgestapt van
brief naar Werkmap?

```sql
SELECT
  oude_kanaalvoorkeur,
  nieuwe_kanaalvoorkeur,
  COUNT(*) AS aantal
FROM gold.uc05_customer_360.kanaalwijzigingen
WHERE wijzig_datum >= CURRENT_DATE - INTERVAL '30' DAY
GROUP BY oude_kanaalvoorkeur, nieuwe_kanaalvoorkeur
ORDER BY aantal DESC;
```

### 4.3 Workflow C — Pieken in klantvraag

```sql
SELECT
  date_trunc('day', contact_datum) AS dag,
  COUNT(*) AS contacten,
  AVG(behandel_duur_min) AS gem_duur
FROM gold.uc05_customer_360.contact_log
WHERE contact_datum >= CURRENT_DATE - INTERVAL '14' DAY
GROUP BY 1
ORDER BY 1;
```

### 4.4 Workflow D — Overzicht voor teamleider

In Superset → dashboard "CRM Trends" → filteren op je team → exporteer als PDF.

> **Niet doen.** Geen lijst met BSN's exporteren — ook niet gemaskeerde.
> Voor teamleider zijn aggregaten genoeg.

### 4.5 Workflow E — Eén cliënt zonder andere data koppelen

Stel een cliënt vraagt: "Wat hebben jullie over mij?" — Beantwoord:

1. Wat **jij** ziet in het 360°-beeld (= een **deel** van het volledige platform image)
2. Verwijs voor volledige inzage naar het AVG-inzageformulier (out-of-platform proces)
3. Geef nooit een uitprint van het scherm — laat zien op het scherm en lees voor

---

## 5. Hulp, fouten & escalatie

### 5.1 Foutmeldingen

| Foutmelding | Betekenis | Actie |
|---|---|---|
| `bsn = NULL` of "uitgegrijsd" | Kolom gemaskeerd, niet gewist | Voor klantidentificatie volstaat naam + birth_date |
| `Access Denied: silver.claims.*` | Andere domeinen niet zichtbaar | Verwijs cliënt door naar WIA-team |
| `Cliënt niet gevonden` | Mogelijk synthesedata-mismatch (referentie-omgeving) | Check spelling, gebruik birth_date |

### 5.2 Wie helpt?

| Probleem | Contact |
|---|---|
| Inloggen / MFA | Platform-admin |
| Cliënt staat niet in 360° | Data-steward (mogelijke ingestion-vertraging) |
| Cliënt vraagt complexe inzage | Verwijs naar AVG-loket UWV |

---

## 6. Wat je nooit doet

- Een volledige BSN noemen aan de telefoon — gebruik gemaskeerde versie.
- Beslissingen nemen over uitkeringen — alleen WIA/WW/Wajong-rollen.
- Schermafbeeldingen mailen, ook niet "even" naar een collega.
- Cliënt-data combineren in eigen Excel — alle analyses gaan via Superset.

---

**Vorige:** [03-claims-analyst.md](03-claims-analyst.md) ·
**Volgende:** [05-finance-analyst.md](05-finance-analyst.md) ·
**Index:** [README.md](README.md)
