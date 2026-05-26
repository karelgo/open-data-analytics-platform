---
title: "Handleiding — Proactief dienstverlener"
role: proactief_dienstverlener
---

> Rol-key: `proactief_dienstverlener` · Domein: Toeslagenwet (proactief) · Risiconiveau toegang: middel (PII, geen medisch)

Deze handleiding is voor **medewerkers die proactief cliënten benaderen
voor TW-eligibility** (Toeslagenwet). De use case (UC-04) gebruikt
voorspelmodellen om cliënten te identificeren die mogelijk recht hebben
maar niet hebben aangevraagd. **Opt-out van de cliënt is leidend.**

---

## 1. Wat doet jouw rol?

Je bekijkt de werklijst van mogelijke TW-rechthebbenden, beoordeelt elke
case en initieert proactief contact. Je gebruikt het platform om:

- De UC-04 werklijst te raadplegen (kandidaten met opt-out reeds gefilterd)
- Per case context te zien (waarom is iemand voorgedragen?)
- Resultaten van eerdere benadering te volgen

> **Mens beslist.** Het model selecteert kandidaten op basis van patronen.
> Jij bepaalt of je belt, en hoe. Het model is **geen** eligibility-besluit.

---

## 2. Inloggen, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Werklijst-dashboard | https://superset.odap.local |
| **OpenMetadata** | Definities, model-info | https://openmetadata.odap.local |

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalog en schema

| Catalog | Schema | Inhoud | Toegang |
|---|---|---|---|
| `gold` | `uc04_tw_eligibility` | Werklijst proactief TW | **Ja** |
| `silver` | * | Niet voor jouw rol | **Nee** |
| `sensitive` | * | (geen) | **Nee** |

### 3.2 Welke kolommen?

In `gold.uc04_tw_eligibility.werklijst`:

| Kolom | Wat zie je? |
|---|---|
| `bsn`, naam, geboortedatum | Volledig — nodig voor klantcontact |
| `adres`, kanaalvoorkeur | Volledig |
| `iban`, `bankrekening` | Gemaskeerd |
| `diagnose`, `icd10` | NULL — niet jouw doel |
| `eligibility_score` | Score uit het model |
| `top_drivers` | Korte uitleg waarom voorgedragen |
| `opt_out` | Altijd `false` — opt-outs zijn al uitgefilterd |
| `laatste_benadering` | Datum / kanaal van vorige poging |

### 3.3 Doelbinding

Purpose: **"proactieve_dienstverlening"**. Je werklijst wordt gefilterd
op cliënten die **niet** opt-out hebben gegeven; opt-out is een rij-filter
op database-niveau, niet een vinkje in de UI.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Werklijst van vandaag

In Superset → dashboard "TW Werklijst" → tegel **Vandaag te benaderen**.

Of via Trino:

```sql
SELECT
  bsn,
  voornaam,
  achternaam,
  geboortedatum,
  kanaalvoorkeur,
  eligibility_score,
  top_drivers,
  laatste_benadering
FROM gold.uc04_tw_eligibility.werklijst
WHERE voor_datum = CURRENT_DATE
ORDER BY eligibility_score DESC
LIMIT 50;
```

### 4.2 Workflow B — Per case context bekijken

**Scenario.** Cliënt 999000234 staat hoog op de lijst. Waarom?

1. Klik in Superset op de rij → **Drill-through naar Detail**.
2. Bekijk **Top drivers**: bv. "WW eindigt over 2 weken; geen TW-aanvraag bekend".
3. Bekijk **Vorige benadering**: bv. "Brief 2026-03-15, geen reactie".
4. Beslis: bel, schrijf, of pak hem niet (cliënt heeft mogelijk al actie ondernomen elders).

### 4.3 Workflow C — Resultaat vastleggen

**Scenario.** Je hebt mevrouw Jansen gebeld; ze gaat een TW-aanvraag indienen.

In de Werkmap (out-of-platform): leg het contact + de uitkomst vast.
Het mart wordt morgen ververst en haar score zal vermoedelijk dalen.

> Je legt **niet** in dit platform direct iets vast — dit is een leesbare
> mart. Vastlegging gaat via Werkmap/CRM.

### 4.4 Workflow D — Effectiviteit van benadering

```sql
SELECT
  benadering_kanaal,
  COUNT(*)                                               AS contacten,
  SUM(CASE WHEN aanvraag_binnen_30d THEN 1 ELSE 0 END)   AS leidde_tot_aanvraag,
  100.0 * SUM(CASE WHEN aanvraag_binnen_30d THEN 1 ELSE 0 END) / COUNT(*) AS conversie_pct
FROM   gold.uc04_tw_eligibility.benadering_uitkomst
WHERE  benadering_datum >= CURRENT_DATE - INTERVAL '90' DAY
GROUP  BY benadering_kanaal
ORDER  BY conversie_pct DESC;
```

### 4.5 Workflow E — Opt-out respecteren

**Scenario.** Cliënt belt: "Bel me niet meer."

1. Geef cliënt door waar opt-out wordt vastgelegd (Werkmap-instellingen / formulier).
2. Werklijst wordt automatisch gefilterd vanaf de eerstvolgende refresh.
3. **Bel deze cliënt niet meer**, ook niet via een andere lijst — het is opt-out, niet opt-out-per-kanaal.

---

## 5. Hulp, fouten & escalatie

| Foutmelding | Betekenis | Actie |
|---|---|---|
| `Access Denied: silver.crm` | Geen ruwe CRM-data | Werk op `gold.uc04_*` |
| `Score = 0` | Opt-out of geen drivers | Niet benaderen |
| `Werklijst leeg` | Kandidaten op = goed nieuws | Pak een team-overzicht |

| Probleem | Contact |
|---|---|
| Inloggen | Platform-admin |
| "De score klopt niet" | Data-steward |
| Cliënt klaagt over benadering | Bias/grievance-kanaal UWV (out-of-platform) |

---

## 6. Wat je nooit doet

- Een cliënt met opt-out toch benaderen via "een ander excuus".
- Werklijst exporteren naar privémail of persoonlijk Excel.
- Cliënt vertellen welke score het model heeft gegeven — dat is intern.
- Beslissen op basis van score alleen — gebruik altijd de drivers en je oordeel.

---

**Vorige:** [06-smz-planner.md](06-smz-planner.md) ·
**Volgende:** [08-researcher.md](08-researcher.md) ·
**Index:** [README.md](README.md)
