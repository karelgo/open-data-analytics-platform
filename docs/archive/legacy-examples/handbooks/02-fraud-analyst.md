# Handbook — Fraud Analyst

> Rol-key: `fraud_analyst` · Domein: WW / Handhaving · Risiconiveau access: hoog (PII + bankrekening)

Deze handbook is voor **handhavers** die WW-claim payouten onderzoeken op
recht- en doelmatigheid. Je hebt access tot WW-data en een aantal
financiële kolommen die voor andere rollen gemaskeerd zijn — zoals
bankrekening-/IBAN-velden voor onderzoeksdoeleinden.

---

--8<-- "_snippets/url-modes.md"

## 1. Wat doet jouw rol?

Je onderzoekt signalen van mogelijk oneigenlijk gebruik van WW-claim payouten.
Je gebruikt het platform om:

- WW-request, betalingen en vermogensvelden te combineren
- Risico-indicatoren from the UC-03-model te raadplegen
- Researchsdossiers samen te stellen
- Caseload-overzichten te bekijken

Je hebt **niet**: medische velden (`diagnose`, `icd10`) en geen access tot
Wajong of WIA. Bankrekening- en IBAN-velden zie je **wel**, maar uitsluitend
voor het doel "handhaving".

---

## 2. Sign in, MFA & applicaties

### 2.1 Account

Accountnaam: `fraud.analyst`. **MFA verplicht** — zelfde TOTP-procedure als
voor andere rollen. Wachtwoord wijzigen bij eerste login.

### 2.2 Welke applicaties gebruik je?

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Dashboards: WW-risico, caseload, signalen | https://superset.odap.local:8443 |
| **OpenMetadata** | Begrippen, eigenaarschap, lineage | https://openmetadata.odap.local:8443 |

> Je gebruikt **niet**: NiFi, Airflow, sensitive vault.

### 2.3 Sessie

Inactiviteits-timeout 30 min, max 8 uur. **Bij elke onderzoeksvraag log je
je doel**: het systeem registreert dat al automatisch (decision-log), maar
goede gewoonte is een korte notitie in je eigen onderzoeksysteem.

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs en schemas waar je in mag

| Catalog | Schema | Wat zit erin? | Zie jij het? |
|---|---|---|---|
| `silver` | `ww` | WW-request, betalingen, status-historie | **Ja** |
| `gold` | `uc03_fraud_risk` | Risico-indicatoren per dossier | **Ja** |
| `silver` | `wia`, `wajong`, `crm` | Andere domeinen | **Nee** |
| `sensitive` | `wajong.*` | Bijzondere persoonsgegevens | **Nee** |

### 3.2 Welke kolommen zie je?

Voor `silver.service_requests.*` en `gold.uc03_fraud_risk.*`:

| Kolom | Wat zie je? | Bijzonderheid |
|---|---|---|
| `bsn`, naam, birth_date, adres | **Volledig** | Doel "handhaving" |
| `iban`, `bankrekening` | **Volledig** | Uniek voor jouw rol — anderen zien `NL**********1234` |
| `diagnose`, `icd10` | **Niet** (kolom-mask returnt NULL) | Medisch is niet jouw doel |
| `regio` | Geen filter — landelijk | Handhaving is niet regio-gebonden |

### 3.3 Voorbeeld — onderscheid met andere rollen

Op `silver.persons.persoon` zien:

| Veld | jij (`fraud_analyst`) | `marketing_analyst` | `finance_analyst` |
|---|---|---|---|
| `bsn` | volledig | gemaskeerd | aggregaat-only (geen ruwe BSN) |
| `iban` | volledig | gemaskeerd | gemaskeerd |
| `diagnose` | NULL | NULL | NULL |

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Nieuwe risicosignalen ophalen

**Scenario.** Beginnen werkdag — welke nieuwe risico-cases zijn er sinds gisteren?

1. Open Superset → **Dashboard "WW Risico"**
2. Filter op: nieuw sinds gisteren, score > 0.7
3. Bekijk top-20 in de tegel **Hoogste scores**
4. Klik door op een rij → **Drill-through naar dossierdetails**

### 4.2 Workflow B — Research op één dossier

**Scenario.** Je hebt een tip ontvangen over BSN 999000456.

```sql
SELECT
  a.bsn,
  a.aanvraag_datum,
  a.status,
  b.iban,
  b.bedrag,
  b.betaal_datum,
  r.score,
  r.top_drivers
FROM silver.service_requests.application a
LEFT JOIN silver.service_requests.betaling b USING (bsn)
LEFT JOIN gold.uc03_fraud_risk.score r USING (bsn)
WHERE a.bsn = '999000456'
ORDER BY b.betaal_datum DESC;
```

### 4.3 Workflow C — Caseload van je team

```sql
SELECT
  team_handhaver,
  COUNT(*)               AS aantal_open,
  AVG(score)             AS gem_score,
  MIN(aanmaak_datum)     AS oudste_signaal
FROM gold.uc03_fraud_risk.actuele_signalen
WHERE status = 'in_onderzoek'
GROUP BY team_handhaver
ORDER BY aantal_open DESC;
```

### 4.4 Workflow D — Researchsdossier samenstellen

**Scenario.** Je hebt voldoende signaal voor formeel onderzoek; je wilt een gestructureerd dossier.

1. Maak een nieuwe **Saved Query** in Superset with the joins van workflow B
2. Exporteer het resultaat als CSV
3. Plaats het CSV in het zaak-dossier in jouw onderzoeksysteem (out-of-platform)
4. Voeg je query in de zaak-aantekening: zo is reproduceerbaar wat je zag

> **Audit-trail.** Het OPA-decision-log registreert je query met timestamp,
> tabellen en kolommen. Jouw onderzoeksysteem registreert het zaak-doel.
> Samen geven ze later een verifieerbaar verhaal: "wie zag wat, wanneer, waarom?"

### 4.5 Workflow E — Vergelijking risicoscore over tijd

```sql
SELECT
  date_trunc('week', score_datum) AS week,
  AVG(score) AS gem_score,
  PERCENTILE_DISC(score, 0.95) WITHIN GROUP (ORDER BY score) AS p95
FROM gold.uc03_fraud_risk.score
WHERE score_datum >= CURRENT_DATE - INTERVAL '90' DAY
GROUP BY 1
ORDER BY 1;
```

---

## 5. Hulp, fouten & escalatie

### 5.1 Veelvoorkomende errors

| Foutmelding | Wat betekent het? | Wat doe je? |
|---|---|---|
| `Access Denied: column 'diagnose' returns NULL` | Medische velden zijn voor jou gemaskeerd | Niet nodig voor handhaving |
| `Access Denied: silver.claims.*` | WIA is niet jouw doel | Vraag een Claims Analyst voor cross-domein vragen |
| `Access Denied: sensitive.*` | Sensitive Vault is afgeschermd | Niet beschikbaar — Wajong-route via collega |
| `Bias / fairness warning op model` | Het UC-03 model heeft een waarschuwing afgegeven | Stop het automatisch gebruik; meld bij data-steward |

### 5.2 Bias en mens-in-de-lus

Het WW-risk-model (UC-03) is een **beslissingsondersteunend systeem**, geen
besluitnemer. Als handhaver beslis jij of een case nader onderzoek krijgt.
Het model levert een score en een korte uitleg (top-drivers). Volg deze regels:

1. Score is een **prioritering**, niet een conclusie.
2. Een score < 0.5 betekent niet "schoon"; je kunt op andere gronden nog steeds
   onderzoek doen.
3. Bij twijfel: hef het automatische signaal op en doe handmatig onderzoek.
4. Modelversies worden gelogd — je kunt achteraf reproduceren welke versie welke score gaf.

### 5.3 Wie helpt waarbij?

| Probleem | Contact |
|---|---|
| Sign in, MFA | Platform-admin |
| Kolom-betekenis | Data-steward |
| "De score klopt niet" | Data-steward → MLOps-team |
| Vermoede inbreuk | Platform-admin (telefonisch) |

---

## 6. Wat je nooit doet

- IBAN-gegevens delen met collega's die er geen doel voor hebben (bv. CRM).
- Een onderzoek starten enkel op basis van een hoge score, zonder eigen oordeel.
- Een PDF-export met BSN's mailen — gebruik het zaak-dossier.
- Bulk-downloads draaien zonder doelvermelding in je zaak-systeem.

---

**Vorige:** [01-claims-analyst.md](01-claims-analyst.md) ·
**Volgende:** [03-claims-analyst.md](03-claims-analyst.md) ·
**Index:** [README.md](README.md)
