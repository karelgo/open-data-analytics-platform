---
title: "Handbook — Data-steward"
role: data_steward
---

> Rol-key: `data_steward` · Domein: Datakwaliteit & governance · Risiconiveau access: hoog (PII voor DQ-controle)

Deze handbook is voor **data-stewards**. Jij bent de spil tussen
data-engineers (die pipelines bouwen) en eindusers (die data
gebruiken). Je zorgt voor kwaliteit, lineage, eigenaarschap en juiste
classificatie. Je ziet PII voor controledoeleinden, **niet** medische data.

---

## 1. Wat doet jouw rol?

Je bewaakt de governance van het platform. Je gebruikt het platform om:

- Datakwaliteit te bewaken (dbt-tests, OpenMetadata-profiler)
- Eigenaarschap, classificaties en purpose-limitationen actueel te houden
- Lineage te valideren (van bron tot dashboard)
- Glossary (CGM-begrippen) te onderhouden
- Sensitive-queries van Claims Analystn te reviewen
- Eindusers te helpen bij begrip en interpretatie van data

---

## 2. Sign in, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **OpenMetadata** | Hoofdworkspace: catalog, glossary, classificaties, profiler, lineage | https://openmetadata.odap.local |
| **Apache Superset** | Dashboards reviewen, ownership-overzichten | https://superset.odap.local |
| **Apache Airflow** | DQ-DAGs draaien | https://airflow.odap.local |
| **OpenSearch (Kibana-achtig)** | OPA-decision-logs reviewen | https://openmetadata.odap.local/logs |
| **dbt CLI / docs** | dbt-tests + lineage-docs | lokaal of via VS Code remote |

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs

| Catalog | Access | Doel |
|---|---|---|
| `bronze` | **Ja** (kwaliteitscontrole) | Vergelijken bron met silver |
| `silver` | **Ja** | DQ-bewaking, profiler |
| `gold` | **Ja** | Validatie van marts |
| `sensitive` | **Nee** | Niet jouw doel — alleen Claims Analystn + admin |
| `sandbox` | **Nee** | Researcher-zone |

### 3.2 Welke kolommen?

PII (BSN, naam, IBAN) zie je **volledig** voor DQ-controle. Medisch
(`diagnose`, `icd10`) zie je **niet** — daarvoor heb je geen doel.

> **Vuistregel.** Je hebt PII-access om datakwaliteit te valideren, niet om
> dossiers te lezen. Steekproeven, niet bulk-exports.

### 3.3 Purpose limitationen

Purposes: **"sturingsinfo"** en **"kwaliteitscontrole"**. Sommige
doel-specifieke marts (UC-04, UC-05) zijn voor jou alleen vanuit
kwaliteitscontrole-perspectief beschikbaar.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Dagstart: DQ-overzicht

1. Open **OpenMetadata** → **Quality** → **Test Suites**.
2. Bekijk welke dbt-tests vannacht faalden (rood).
3. Per fout: klik door to the testbeschrijving + de records die faalden.

Of via Trino:

```sql
SELECT
  test_name,
  failures,
  last_run
FROM   gold.uc07_dq_policies.test_resultaten_daily
WHERE  status = 'failed'
ORDER  BY last_run DESC;
```

### 4.2 Workflow B — Profiler-vlag uitzoeken

**Scenario.** OpenMetadata toont rood vlag op `silver.claims.application.regio`:
"5% NULL, vorige week 0.2%". Je gaat onderzoeken.

```sql
-- Hoeveel NULL?
SELECT
  date_trunc('day', aanvraag_datum) AS dag,
  100.0 * SUM(CASE WHEN regio IS NULL THEN 1 ELSE 0 END) / COUNT(*) AS null_pct
FROM   silver.claims.application
WHERE  aanvraag_datum >= CURRENT_DATE - INTERVAL '14' DAY
GROUP  BY 1
ORDER  BY 1;
```

Vermoeden: ingestion-issue. Je escaleert to the data-engineer.

### 4.3 Workflow C — Sensitive-review

**Dagelijks om 9:00.** Open OpenSearch / OPA decision-log:

```
filter: catalog="sensitive" AND user_role="claims_analyst"
       AND timestamp >= "yesterday"
```

Bekijk per query: doel, tijdstip, gebruiker, kolommen. Vraag bij twijfel
de arbeidsdeskundige om context. Anomalieën meld je bij platform-admin.

### 4.4 Workflow D — Eigenaarschap actueel houden

1. Open OpenMetadata → **Governance** → **Ownership Coverage**.
2. Filter op tabellen zonder eigenaar.
3. Per tabel: vraag het domein-team wie de eigenaar wordt.
4. Leg vast in OpenMetadata.

### 4.5 Workflow E — Glossary-term toevoegen

**Scenario.** Het beleidsteam introduceert begrip "Voorschot-WIA-gehalte".

1. Open OpenMetadata → **Glossary** → **CGM**.
2. Voeg term toe: definitie, eigenaar, gerelateerd aan welke kolommen.
3. Koppel de term aan `silver.claims.voorschot.bedrag`.
4. Communiceer naar users (e-mail of dashboard-update).

### 4.6 Workflow F — Lineage valideren

```sql
-- Welke marts hangen van silver.claims.application?
SELECT downstream_table
FROM   metadata.lineage
WHERE  upstream_table = 'silver.claims.application';
```

Of in OpenMetadata: klik **Lineage** op `silver.claims.application` en zie alle
downstream-marts en dashboards.

### 4.7 Workflow G — DPIA-evidence verzamelen

Voor periodieke audits exporteer je:

- OPA-test-resultaten (`make opa-test`, 23/23 PASS)
- OpenMetadata classifications-export
- dbt-test-history van de laatste 30 dagen
- Decision-log statistieken

Zie [`docs/runbook.md` § 10](../runbook.md) for the volledige procedure.

---

## 5. Verantwoordelijkheden in volgorde van prioriteit

1. **Kwaliteit van production-zones** (silver/gold) — fouten hier raken besluiten.
2. **Sensitive-review** — dagelijks, 1e taak van de ochtend.
3. **Eigenaarschap-coverage** — > 95% van datasets moet een eigenaar hebben.
4. **DPIA-evidence** — actueel en toegankelijk voor toezichthouders.
5. **Glossary-onderhoud** — users moeten begrippen kunnen vinden.

---

## 6. Hulp, fouten & escalatie

| Probleem | Wat doe je? |
|---|---|
| dbt-test faalt structureel | Pair met data-engineer; los root-cause op, niet alleen test |
| Eigenaarschap-gap > 5% | Maak escalatielijst voor domein-leads |
| Sensitive-query buiten patroon | Bel platform-admin + arbeidsdeskundige (niet via mail) |
| Profiler-piek (NULL/duplicaten) | Open ticket bij data-engineer; flag in Slack `#dq-alerts` |
| Eindgebruiker vraagt access | Verwijs naar role-aanvraagprocedure (out-of-platform) |

| Probleem | Contact |
|---|---|
| Pipeline-issue | Data-engineer |
| Cluster-issue | Platform-admin |
| Beleid/wettelijke vraag | Data Office / privacy-officer |

---

## 7. Wat je nooit doet

- Een sensitive-query bekijken om "interessante cases" te vinden.
- PII-data exporteren naar je laptop voor DQ-werk — werk altijd in Trino.
- Een dbt-test "even disable-en" om een release te halen — los root-cause op.
- Eigenaarschap aan jezelf toewijzen voor alle datasets — eigenaar is het domein-team.

---

**Vorige:** [08-researcher.md](08-researcher.md) ·
**Volgende:** [10-data-engineer.md](10-data-engineer.md) ·
**Index:** [README.md](README.md)
