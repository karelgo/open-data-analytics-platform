---
title: "Handbook — Operations Manager"
role: operations_manager
---

> Rol-key: `operations_manager` · Domein: Operationale zaken · Risiconiveau access: laag (geen cliënt-PII)

Deze handbook is voor **planners die SMZ-capaciteit beheren**:
verzekeringsartsen, arbeidsdeskundigen, roosters en wachttijden. Je werkt
op **planningsdata zonder cliënt-PII** — je ziet wel beoordelaar-roosters
en case-counts, maar geen individuele dossiers.

---

## 1. Wat doet jouw rol?

Je plant SMZ-capaciteit per regio en specialisme. UC-08 levert het mart
waar je op werkt. Je gebruikt het platform om:

- Roosters van verzekeringsartsen en arbeidsdeskundigen te zien
- Wachttijden, voorraad en doorlooptijd op team/regio-niveau te volgen
- Capaciteits-scenario's te modelleren
- Geen cliënt-dossiers te raadplegen

---

## 2. Sign in, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Capaciteits-dashboards | https://superset.odap.local |
| **OpenMetadata** | Definities | https://openmetadata.odap.local |

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs en schemas

| Catalog | Schema | Inhoud | Access |
|---|---|---|---|
| `gold` | `uc08_capacity_planning` | Capaciteits-aggregaten | **Ja** |
| `silver` | `smz` | SMZ-rooster en case-counts | **Ja** |
| `silver` | `wia`, `ww`, `wajong`, `crm` | Cliënt-dossiers | **Nee** |
| `sensitive` | * | (geen) | **Nee** |

### 3.2 Welke kolommen?

In `gold.uc08_capacity_planning.*` en `silver.smz.*`:

| Kolom | Wat zie je? |
|---|---|
| `beoordelaar_id` | Pseudoniem (geen naam) |
| `team`, `regio`, `specialisme` | Volledig — voor planning |
| `rooster_uren` | Volledig |
| `caseload_aantal` | Aggregaat-aantal |
| `wachttijd_dagen` | Mediane/gem. wachttijd |
| `bsn`, naam, diagnose, etc. | NULL (kolom-mask) — geen cliënt-PII |
| `doorlooptijd_dagen` (geaggregeerd) | Volledig |

### 3.3 Purpose limitation

Purpose: **"planning"**. Je rol kan dus geen behandelingsdoelen aanspreken.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Wachttijd per regio

```sql
SELECT
  regio,
  specialisme,
  PERCENTILE_DISC(wachttijd_dagen, 0.5) WITHIN GROUP (ORDER BY wachttijd_dagen) AS p50,
  PERCENTILE_DISC(wachttijd_dagen, 0.95) WITHIN GROUP (ORDER BY wachttijd_dagen) AS p95,
  COUNT(*)                               AS aantal_cases
FROM   gold.uc08_capacity_planning.wachttijd
WHERE  peildatum = CURRENT_DATE
GROUP  BY regio, specialisme
ORDER  BY p95 DESC;
```

### 4.2 Workflow B — Roosterbezetting

```sql
SELECT
  team,
  date_trunc('week', week_start) AS week,
  SUM(rooster_uren)              AS gepland,
  SUM(beschikbaar_uren)          AS beschikbaar,
  SUM(rooster_uren) * 1.0 / NULLIF(SUM(beschikbaar_uren), 0) AS bezet_pct
FROM   silver.smz.rooster
WHERE  week_start >= CURRENT_DATE - INTERVAL '8' WEEK
GROUP  BY team, date_trunc('week', week_start)
ORDER  BY team, week;
```

### 4.3 Workflow C — Capaciteits-scenario

**Scenario.** Wat als specialisme A 10% extra capaciteit krijgt — hoeveel
zakt de p95-wachttijd?

```sql
WITH huidige AS (
  SELECT specialisme, AVG(wachttijd_dagen) AS gem
  FROM   gold.uc08_capacity_planning.wachttijd
  WHERE  specialisme = 'verzekeringsarts'
  GROUP  BY specialisme
),
scenario AS (
  SELECT
    specialisme,
    gem * 0.90  AS verwacht_minus_10pct
  FROM huidige
)
SELECT * FROM scenario;
```

### 4.4 Workflow D — Voorraad-piek detecteren

In Superset → dashboard "SMZ Capaciteit" → tegel **Voorraad per team**.
Filter op je eigen regio's. Bij rode tegels: bel je teamleider.

### 4.5 Workflow E — Maandrapport

Standaard rapport in Superset, downloaden als PDF, mailen naar je
teamleider — geen BSN's, alleen aggregaten.

---

## 5. Hulp, fouten & escalatie

| Foutmelding | Betekenis | Actie |
|---|---|---|
| `Access Denied: silver.claims.application` | Cliënt-data niet voor planning | Werk op aggregaat-mart |
| `bsn IS NULL` | Kolom gemaskeerd | Niet nodig voor planning |

| Probleem | Contact |
|---|---|
| Sign in | Platform-admin |
| Definities | Data-steward |
| Onverwachte wachttijdpiek | Teamleider (operationeel), data-steward (data) |

---

## 6. Wat je nooit doet

- Beoordelaars op naam koppelen aan caseload — dat is HR, niet jouw rol.
- BSN's in planningsoutput zetten — die heb je niet.
- Capaciteitsdata extern delen zonder regio-aggregatie.

---

**Vorige:** [05-finance-analyst.md](05-finance-analyst.md) ·
**Volgende:** [07-marketing-analyst.md](07-marketing-analyst.md) ·
**Index:** [README.md](README.md)
