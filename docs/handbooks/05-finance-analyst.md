# Handleiding — Finance Analyst

> Rol-key: `finance_analyst` · Domein: Financiën / Beleid · Risiconiveau toegang: laag (alleen aggregaten, geen PII)

Deze handleiding is voor **financieel-economische analisten** die werken
aan schadelast, prognoses en beleidsanalyses. Je werkt op **geaggregeerde
data**: geen ruwe BSN, geen individuele uitkeringsbedragen.

---

--8<-- "_snippets/url-modes.md"

## 1. Wat doet jouw rol?

Je maakt prognoses voor schadelast, doorrekent beleidsscenario's en levert
input voor begrotingen. Je gebruikt het platform om:

- UC-06 lastprognose-mart te raadplegen
- Scenario-analyses te draaien op aggregaten
- Trends in instroom/uitstroom te volgen
- Geen individuele dossiers te zien

---

## 2. Inloggen, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Dashboards: schadelast, prognoses | https://superset.odap.local:8443 |
| **OpenMetadata** | Definities, eigenaarschap | https://openmetadata.odap.local:8443 |

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalog en schema

| Catalog | Schema | Inhoud | Toegang |
|---|---|---|---|
| `gold` | `uc06_lastprognose` | Schadelast-aggregaten en prognoses | **Ja** |
| `silver` | * | PII en domein-data | **Nee** |
| `bronze`, `sensitive` | * | (geen) | **Nee** |

### 3.2 Geen PII — wat dan wel?

Je werkt op aggregaten:

| Kolom | Voorbeeld |
|---|---|
| `regeling` | "WW", "WIA-IVA", "WIA-WGA", "Wajong" |
| `regio` | NUTS-3 regio's |
| `leeftijdsgroep` | Buckets van 5 jaar |
| `instroom_aantal` | Aantal nieuwe instromers per maand |
| `uitstroom_aantal` | Aantal uitstroom per maand |
| `gem_duur_dagen` | Gemiddelde uitkeringsduur |
| `totale_last_eur` | Totaal uitbetaald per maand |
| `prognose_komende_12_mnd` | Prognose-getallen |

> **Geen ruwe BSN.** Het platform weigert je rauwe persoons-queries
> (`silver.persoon.*`) — niet jouw doel.

### 3.3 Doelbinding

Purposes: **"actuarie"** en **"beleid"**. Modellen in `gold.uc06_*` zijn
gemarkeerd met deze purposes; queries op andere marts zonder geldig doel
worden geweigerd.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Schadelast huidig jaar

```sql
SELECT
  regeling,
  date_trunc('month', maand) AS maand,
  SUM(totale_last_eur)       AS last
FROM   gold.uc06_lastprognose.maandlast
WHERE  jaar = YEAR(CURRENT_DATE)
GROUP  BY regeling, date_trunc('month', maand)
ORDER  BY regeling, maand;
```

### 4.2 Workflow B — Prognose-scenario doorrekenen

```sql
WITH base AS (
  SELECT regeling, prognose_komende_12_mnd
  FROM   gold.uc06_lastprognose.prognose_basis
  WHERE  prognose_datum = CURRENT_DATE
)
SELECT
  regeling,
  prognose_komende_12_mnd                               AS basis,
  prognose_komende_12_mnd * 1.05                        AS plus_5pct,
  prognose_komende_12_mnd * 0.95                        AS min_5pct
FROM base
ORDER BY regeling;
```

### 4.3 Workflow C — Trends per leeftijdsgroep

```sql
SELECT
  leeftijdsgroep,
  jaar,
  SUM(instroom_aantal) AS instroom
FROM   gold.uc06_lastprognose.instroom_per_groep
WHERE  jaar BETWEEN 2022 AND 2025
GROUP  BY leeftijdsgroep, jaar
ORDER  BY leeftijdsgroep, jaar;
```

### 4.4 Workflow D — Beleidsmemo-tabel

1. Trek aggregaat in Superset SQL Lab.
2. Exporteer als CSV.
3. Plakken in Word/Excel voor beleidsmemo.
4. Bewaar je query als Saved Query met titel + datum — dit is je trail.

### 4.5 Workflow E — Validatie van prognose

```sql
-- Vergelijk prognose-vorig-kwartaal met realiteit
SELECT
  regeling,
  prognose                AS p,
  realisatie              AS r,
  realisatie - prognose   AS afwijking
FROM gold.uc06_lastprognose.prognose_validatie
WHERE peilkwartaal = '2026-Q1';
```

---

## 5. Hulp, fouten & escalatie

| Foutmelding | Betekenis | Actie |
|---|---|---|
| `Access Denied: silver.persoon.*` | Geen PII voor jouw rol | Werk op aggregaat-marts |
| `Access Denied: gold.uc05_client_360` | Andere doelbinding | Niet jouw scope |
| `Result has only 8 rows` | Te kleine groep, mogelijk privacy-onderdrukking | Aggregeer ruwer |

| Probleem | Contact |
|---|---|
| Inloggen, MFA | Platform-admin |
| Definitie van een prognose-veld | Data-steward |
| "De cijfers verschillen van Werkmap" | Data-steward (kwaliteit) |

---

## 6. Wat je nooit doet

- Aggregaten op kleine groepen (< 10) extern delen — herleidbaarheid.
- Querys op `silver.persoon.*` proberen "om het toch te zien".
- CSV-exports met cliënt-detail laten — jij ziet die niet, maar valideer altijd.

---

**Vorige:** [04-marketing-analyst.md](04-marketing-analyst.md) ·
**Volgende:** [06-operations-manager.md](06-operations-manager.md) ·
**Index:** [README.md](README.md)
