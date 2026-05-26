---
title: "Handleiding — Researcher"
role: researcher
---

> Rol-key: `researcher` · Domein: Statistisch onderzoek (sandbox) · Risiconiveau toegang: laag (alleen sandbox, gepseudonimiseerd)

Deze handleiding is voor **onderzoekers** die statistisch onderzoek doen
op ODAP data. Je werkt **uitsluitend in de sandbox-zone** met
gepseudonimiseerde panels — geen productie-PII, geen rauwe BSN's.

---

## 1. Wat doet jouw rol?

Je doet wetenschappelijk-statistisch onderzoek (UC-09 — re-integratie-effectiviteit
en vergelijkbare studies). Je gebruikt het platform om:

- Gepseudonimiseerde panels uit `sandbox.*` te raadplegen
- Cohort-analyses, regressies en controlled comparisons te draaien
- Resultaten alleen geaggregeerd te exporteren

> Als je rauwe productie-data nodig hebt, ben je in de **verkeerde rol**.
> Vraag dan een formele DPIA-aanvraag bij Data Office; deze wordt buiten
> dit platform afgehandeld.

---

## 2. Inloggen, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Dashboards en SQL Lab | https://superset.odap.local |
| **OpenMetadata** | Definities, lineage van panels | https://openmetadata.odap.local |

Tip: Trino integreert met Python-notebooks via `trino-python-client`. Voor
reproduceerbaar onderzoek: bewaar je notebook + queries bij je publicatie.
Voor ad-hoc gebruik van Trino: `kubectl -n odap-platform port-forward svc/trino-coordinator 8443:8443` en verbind op `localhost:8443`.

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalog en schema

| Catalog | Schema | Inhoud | Toegang |
|---|---|---|---|
| `sandbox` | * | Gepseudonimiseerde panels, synthetische cohorts | **Ja** |
| `silver`, `gold`, `bronze`, `sensitive` | * | Productie-zones | **Nee** |

### 3.2 Welke kolommen?

In `sandbox.*`:

| Kolom | Wat zie je? |
|---|---|
| `bsn_pseudo` | Hash + zout — niet herleidbaar zonder sleutel (die jij niet hebt) |
| `cohort_id` | Anoniem cohort-label |
| `leeftijd_groep`, `regio` | Gegroepeerd |
| `traject_soort`, `uitkomst` | Volledig — kern van je analyse |
| `bsn`, naam, etc. | NIET aanwezig — bij ingestion al verwijderd |

### 3.3 Doelbinding

Purpose: **"statistisch_onderzoek"**. Het platform staat geen joins toe
tussen `sandbox.*` en productiezones — die paden zijn fysiek dichtgezet.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Cohort-overzicht

```sql
SELECT
  cohort_id,
  COUNT(*)               AS n,
  AVG(leeftijd)          AS gem_leeftijd,
  COUNT(*) FILTER (WHERE traject_soort = 'IPS') AS ips_n
FROM   sandbox.uc09.cohort_panel
GROUP  BY cohort_id;
```

### 4.2 Workflow B — Effectiviteits-vergelijking

```sql
SELECT
  traject_soort,
  COUNT(*)                                                         AS n,
  AVG(CASE WHEN werkhervatting_12mnd THEN 1.0 ELSE 0.0 END)        AS slaag_pct,
  STDDEV(CASE WHEN werkhervatting_12mnd THEN 1.0 ELSE 0.0 END)     AS std
FROM   sandbox.uc09.uitkomsten_panel
WHERE  start_jaar = 2024
GROUP  BY traject_soort
HAVING COUNT(*) >= 100         -- pas op kleine groepen
ORDER  BY slaag_pct DESC;
```

### 4.3 Workflow C — Regressie via Python-notebook

```python
# Eerst port-forwarden: kubectl -n odap-platform port-forward svc/trino-coordinator 8443:8443
import trino, pandas as pd, statsmodels.api as sm

conn = trino.dbapi.connect(
    host="localhost", port=8443,
    user="researcher",
    auth=trino.auth.OAuth2Authentication(),  # via Keycloak
    catalog="sandbox", schema="uc09",
)

df = pd.read_sql("""
  SELECT leeftijd, opleidingsniveau, traject_soort, werkhervatting_12mnd
  FROM uitkomsten_panel
  WHERE start_jaar = 2024
""", conn)

X = pd.get_dummies(df[["leeftijd","opleidingsniveau","traject_soort"]], drop_first=True)
X = sm.add_constant(X)
y = df["werkhervatting_12mnd"].astype(int)
res = sm.Logit(y, X).fit()
print(res.summary())
```

### 4.4 Workflow D — Controlled comparison

```sql
WITH gematched AS (
  SELECT
    a.bsn_pseudo, a.traject_soort, a.werkhervatting_12mnd,
    b.bsn_pseudo AS ctrl_pseudo
  FROM sandbox.uc09.uitkomsten_panel a
  JOIN sandbox.uc09.uitkomsten_panel b
    ON  abs(a.leeftijd - b.leeftijd) <= 2
   AND  a.opleidingsniveau = b.opleidingsniveau
   AND  a.regio = b.regio
   AND  a.traject_soort = 'IPS'
   AND  b.traject_soort = 'proefplaatsing'
)
SELECT COUNT(*) FROM gematched;
```

### 4.5 Workflow E — Reproduceerbaar publiceren

1. Houd je SQL + notebook in versiebeheer (Git).
2. Bij publicatie: deel de **anonieme query**, niet de cohort-data.
3. Voor externe data-deling: vraag de Data Office om een formele DPIA-route.

---

## 5. Hulp, fouten & escalatie

| Foutmelding | Betekenis | Actie |
|---|---|---|
| `Access Denied: silver.*` | Productie-data niet voor researcher | Werk in sandbox |
| `JOIN across catalogs not allowed` | Bewust geblokkeerd | Vraag Data Office voor combinatie-traject |
| `Result has < 30 rows` | Mogelijk privacy-onderdrukking | Aggregeer ruwer |

| Probleem | Contact |
|---|---|
| Inloggen | Platform-admin |
| Cohort-vraag, panel-versies | Data Office (out-of-platform) |
| "Ik heb productie-data nodig" | DPIA-aanvraag via Data Office |

---

## 6. Wat je nooit doet

- Pseudoniemen koppelen aan externe data om te de-anonimiseren — strafbaar.
- Cohort-data extern delen zonder Data Office-akkoord.
- Aggregaten met < 10 records publiceren.
- Toegang tot productie-zones forceren via een ander account.

---

**Vorige:** [07-marketing-analyst.md](07-marketing-analyst.md) ·
**Volgende:** [09-data-steward.md](09-data-steward.md) ·
**Index:** [README.md](README.md)
