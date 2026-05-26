# Handboek — UWV Referentie Data- en Analyseplatform per rol

**Eén gebundeld handboek met alle 12 rollen.**

> Dit document bundelt alle per-rol handleidingen achter elkaar. Voor het
> delen met één specifieke gebruiker is de aparte rol-handleiding vaak
> handiger; dit handboek is bedoeld voor distributie naar het hele team,
> bibliotheek-archief, of als training-materiaal.

---

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

--8<-- "_snippets/url-modes.md"

## Overzicht van rollen

Het platform onderscheidt **11 menselijke rollen** + **1 systeemrol**, gemodelleerd
in [`infrastructure/helm/keycloak/realm.json`](../../infrastructure/helm/keycloak/realm.json)
en [`opa-policies-src/data/role_mappings.json`](../../opa-policies-src/data/role_mappings.json).

### Business-rollen (eindgebruikers)

1. **Claims Analyst** — AG / WIA — beoordeelt WIA-aanvragen, ziet PII en medisch in eigen regio
2. **Fraud Analyst** — WW / Handhaving — onderzoekt signalen, ziet bankrekening voor onderzoek
3. **Claims Analyst** — AG / Wajong — Sensitive Vault (4-eyes), ziet medisch
4. **Marketing Analyst** — Klantcontact — werkt met 360°-cliëntbeeld, BSN gemaskeerd
5. **Finance Analyst** — Financiën / Beleid — alleen aggregaten, geen PII
6. **Operations Manager** — Sociaal-medische zaken — capaciteitsplanning, geen cliënt-PII
7. **Marketing Analyst** — Toeslagenwet — werklijst-rol, opt-out gerespecteerd
8. **Researcher** — Onderzoek — alleen sandbox, gepseudonimiseerde panels

### Technische rollen (platform-team)

9. **Data-steward** — datakwaliteit, governance, lineage, sensitive-review
10. **Data-engineer** — pipelines, ingestion, transformaties, JIT op bronze
11. **Platform-admin** — cluster, security, break-glass, incident-respons

### Systeemrol

12. **Smoketest** — service-account voor automated tests + dbt-runs (geen mens)

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


---



## Handleiding — Claims Analyst

> Rol-key: `claims_analyst` · Domein: AG / WIA · Risiconiveau toegang: hoog (PII + medisch)

Deze handleiding is voor **verzekeringsartsen, arbeidsdeskundigen en
beoordelaars** die WIA-aanvragen behandelen. Je gebruikt het platform om
dossiers te raadplegen, voorraad en doorlooptijden in jouw regio te bewaken
en sturingsinformatie op te vragen.

---

## 1. Wat doet jouw rol?

Je beoordeelt of een aanvrager recht heeft op WIA en, zo ja, in welke
categorie (IVA, WGA volledig, WGA gedeeltelijk). Je gebruikt het platform om:

- Lopende WIA-aanvragen in jouw regio in te zien
- Doorlooptijden, wachtgelden en voorraad te bewaken
- Sturingsinformatie te genereren voor je teamleider
- Geanonimiseerde overzichten te maken voor capaciteitsplanning

Je hebt **geen** toegang tot dossiers buiten je eigen regio en geen toegang
tot de Sensitive Vault (`sensitive.*`) — die is voor de Claims Analyst.

---

## 2. Inloggen, MFA & applicaties

### 2.1 Account

Je accountnaam is `claims.analyst` (in productie: je eigen platform account, gefedereerd via SSO).
Het wachtwoord wijzig je bij eerste inlog. **MFA is verplicht** —
configureer een TOTP-app (Google Authenticator, Microsoft Authenticator, 1Password etc.).

### 2.2 Welke applicaties gebruik je?

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Dashboards bekijken: WIA-funnel, doorlooptijden | https://superset.odap.local:8443 |
| **OpenMetadata** | Opzoeken welke kolom wat betekent, wie eigenaar is | https://openmetadata.odap.local:8443 |

> Je gebruikt **niet**: NiFi (ingestion), Airflow (orchestratie). Die zijn voor het platform-team.

### 2.3 Eerste keer inloggen — stappen

1. Open https://superset.odap.local:8443
2. Klik **Inloggen via Keycloak (UWV)**
3. Vul gebruikersnaam + wachtwoord; bij eerste login wijzig je het wachtwoord
4. Scan de QR-code met je TOTP-app en bevestig de eerste 6-cijferige code
5. Je belandt op de Superset-startpagina; rechts staat je rol: **WIA Beoordelaar**

### 2.4 Sessie & timeout

- Inactiviteits-timeout: **30 minuten**
- Maximale sessieduur: **8 uur**
- Bij verlopen sessie: opnieuw inloggen via Keycloak — Superset/Trino starten een fresh OIDC-flow

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs en schemas waar je in mag

| Catalog | Schema | Wat zit erin? | Zie jij het? |
|---|---|---|---|
| `silver` | `wia` | Geconformeerde WIA-aanvragen, beoordelingen, status-historie | **Ja** (jouw regio) |
| `gold` | `uc01_wia_funnel` | Sturingsmart: voorraad, doorlooptijden, voorspelling | **Ja** |
| `silver` | `ww`, `wajong`, `crm`, ... | Andere domeinen | **Nee** |
| `sensitive` | `wajong.*` | Sociaal-medisch dossier Wajong | **Nee** |
| `bronze` | alles | Ruwe brondata | **Nee** |

### 3.2 Welke kolommen zie je?

Voor `silver.wia.aanvraag` en `gold.uc01_wia_funnel.*`:

| Kolom | Wat zie je? | Waarom? |
|---|---|---|
| `bsn` | **Volledig** | Je hebt PII-doel "uitkering/behandeling/reintegratie" |
| `voornaam`, `achternaam` | Volledig | Idem |
| `geboortedatum` | Volledig | Idem |
| `straat`, `huisnummer` | Volledig | Idem |
| `iban`, `bankrekening` | **GEMASKEERD** (bv. `NL**********1234`) | Jij beoordeelt geen betalingen — die staat bij FEZ |
| `diagnose`, `icd10` | Volledig (alleen voor je eigen regio) | Medisch noodzakelijk voor WIA-beoordeling |
| `regio` | Filter — **alleen jouw regio's** | Doelbinding regio-gebonden |

> **Rij-filter (regio_filter).** Het platform past automatisch een rij-filter toe:
> `WHERE regio IN (jouw toegewezen regio's)`. Je hoeft dit niet zelf te schrijven.
> Een query op heel Nederland levert alleen jouw regio op — geen foutmelding.

### 3.3 Wat zie je echt **niet**?

- WW-data (`silver.ww.*`) — andere doelbinding (handhaving, niet WIA)
- Wajong sensitive (`sensitive.wajong.*`) — alleen Claims Analystn
- Bankrekening- en IBAN-velden onmasked — niet nodig voor WIA-beoordeling
- Bronze-laag (`bronze.*`) — alleen voor data-engineers met JIT-toegang
- Andere regio's dan die jou zijn toegewezen

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Voorraad en doorlooptijden bekijken

**Scenario.** Het is maandagochtend, je wilt weten hoeveel aanvragen er
deze week binnenkwamen en hoeveel langer dan 8 weken open staan.

1. Open **Superset** → linker menu → **Dashboards** → **WIA Funnel**
2. Filter rechtsboven op:
   - Periode: laatste 7 dagen
   - Regio: (al automatisch ingesteld op jouw regio's)
3. Bekijk de tegels:
   - **Nieuwe aanvragen deze week** (totaal + verschil met vorige week)
   - **Open > 8 weken** (de wettelijke termijn)
   - **Voorspelde instroom volgende week**

Wil je de onderliggende data zien? Klik **View as table** op een tegel.

### 4.2 Workflow B — Eén dossier opzoeken

**Scenario.** Een collega vraagt om dossier-context voor BSN 999000123.

In **Superset SQL Lab** of **DBeaver naar Trino**:

```sql
SELECT
  bsn,
  voornaam,
  achternaam,
  geboortedatum,
  aanvraag_datum,
  status,
  diagnose,
  regio
FROM silver.wia.aanvraag
WHERE bsn = '999000123';
```

Lever je geen rij op? Mogelijk valt deze BSN buiten jouw regio
(rij-filter werkt). Vraag je teamleider of een collega in de juiste regio.

### 4.3 Workflow C — Eigen team vergelijken met regio

**Scenario.** Je wilt weten hoe jouw team scoort op gemiddelde doorlooptijd
ten opzichte van het regio-gemiddelde.

```sql
SELECT
  team,
  AVG(doorlooptijd_dagen) AS gem_doorlooptijd,
  COUNT(*)               AS aantal_aanvragen
FROM gold.uc01_wia_funnel.afgehandeld
WHERE afhandel_datum >= DATE '2026-04-01'
GROUP BY team
ORDER BY gem_doorlooptijd DESC;
```

> Tip: bewaar je query als **Saved Query** in Superset zodat je hem volgende
> week makkelijk opnieuw draait.

### 4.4 Workflow D — Sturingsrapport voor je teamleider

**Scenario.** Je teamleider vraagt elke maand een rapport "WIA Funnel — regio Noord".

1. Open dashboard **WIA Funnel**
2. Stel filters: periode = vorige maand
3. Rechtsboven: **Download → PDF** (Superset 4.1+)
4. Mail het PDF naar je teamleider, niet via Slack of WhatsApp

> **Niet doen:** copy/paste van een tabel met BSN's in een mail. Gebruik altijd
> aggregaten of geanonimiseerde rapporten voor distributie.

### 4.5 Workflow E — Begrip opzoeken in OpenMetadata

**Scenario.** Wat is precies "datum_aanvraag" versus "datum_eerste_dag"? Welke is leidend?

1. Open https://openmetadata.odap.local:8443
2. Zoek op `mart_uc01_wia_funnel_daily` of op kolomnaam
3. Bij elke kolom zie je: **definitie**, **eigenaar** (data-steward), **bron-tabel**,
   **bewaartermijn**, **classificatie**
4. Klik **Lineage** om de keten van bron → mart te zien

---

## 5. Veelgebruikte queries (kort)

```sql
-- Aantal aanvragen per status, jouw regio's automatisch
SELECT status, COUNT(*) FROM silver.wia.aanvraag GROUP BY status;

-- Dossiers > 8 weken open
SELECT bsn, aanvraag_datum, status
FROM   silver.wia.aanvraag
WHERE  status = 'open'
  AND  aanvraag_datum < CURRENT_DATE - INTERVAL '56' DAY;

-- Top-10 ICD-10 categorieën
SELECT icd10, COUNT(*) AS n
FROM   silver.wia.beoordeling
GROUP  BY icd10
ORDER  BY n DESC LIMIT 10;
```

---

## 6. Hulp, fouten & escalatie

### 6.1 Veelvoorkomende foutmeldingen

| Foutmelding | Wat betekent het? | Wat doe je? |
|---|---|---|
| `Access Denied: cannot select from gold.uc02_wajong.*` | Je probeert Wajong te lezen — niet jouw rol | Niets — vraag een Claims Analyst |
| `Access Denied: regio = 'Zuid' niet toegestaan` | Je rij-filter blokkeert dit, BSN valt buiten je regio | Vraag een collega in de juiste regio |
| `Access Denied: column 'iban' is masked` | Je probeert IBAN onmasked te zien — niet voor WIA | Leef met de mask, of vraag FEZ |
| `Authentication failed: token expired` | OIDC-token is verlopen | Log opnieuw in via Keycloak |
| `Error: schema 'wia' not found` | Trino-catalog niet bereikbaar | Vraag platform-admin (zie 6.3) |

### 6.2 Wat doe je bij een vermoede inbreuk?

Vermoed je dat iemand toegang heeft die niet zou moeten, of zie je data die
je niet zou mogen zien?

1. **Stop met kijken** — niet doorklikken, niet downloaden
2. Maak **één** screenshot van je scherm voor bewijsvoering (geen BSN's expliciet)
3. **Bel** de platform-admin (`platform.admin@odap.local:8443`, niet via mail)
4. Schrijf binnen 24 uur een korte notitie van wat, wanneer, waar

### 6.3 Wie helpt waarbij?

| Probleem | Contact |
|---|---|
| Inloggen lukt niet, MFA-app weg | Platform-admin |
| Vraag over kolom-betekenis | Data-steward |
| "Ik denk dat de data fout is" | Data-steward (kwaliteitscontrole-doelbinding) |
| Trino is traag | Platform-admin |
| Dashboard ontbreekt | Data-steward / dashboard-eigenaar |
| Vermoede beveiligingsincident | Platform-admin (telefonisch) |

---

## 7. Wat je nooit doet

- Een dossier inzien zonder zaakreden — toegang ≠ rechtvaardiging.
- BSN's mailen, in chats plakken of in shared documenten zetten.
- Schermafbeeldingen met persoonsgegevens delen — ook niet "even" voor een bug-rapport.
- Wachtwoorden of TOTP-secrets delen, ook niet met je teamleider.
- Inloggen op een onbeheerd device — sluit altijd je sessie af.

---

## 8. Verantwoordelijkheid (kort)

Je rol staat onder **doelbinding "uitkering" / "behandeling" / "reintegratie"**
(art. 6 lid 1e + art. 9 lid 2h AVG). Elke query wordt gelogd. Steekproefsgewijs
toetst de data-steward of de queries passen bij jouw caseload. Onverwacht
massaal data lezen valt op.

---

**Volgende handleiding:** [02-fraud-analyst.md](02-fraud-analyst.md) ·
**Index:** [README.md](README.md)

---


## Handleiding — Fraud Analyst

> Rol-key: `fraud_analyst` · Domein: WW / Handhaving · Risiconiveau toegang: hoog (PII + bankrekening)

Deze handleiding is voor **handhavers** die WW-uitkeringen onderzoeken op
recht- en doelmatigheid. Je hebt toegang tot WW-data en een aantal
financiële kolommen die voor andere rollen gemaskeerd zijn — zoals
bankrekening-/IBAN-velden voor onderzoeksdoeleinden.

---

## 1. Wat doet jouw rol?

Je onderzoekt signalen van mogelijk oneigenlijk gebruik van WW-uitkeringen.
Je gebruikt het platform om:

- WW-aanvragen, betalingen en vermogensvelden te combineren
- Risico-indicatoren uit het UC-03-model te raadplegen
- Onderzoeksdossiers samen te stellen
- Caseload-overzichten te bekijken

Je hebt **niet**: medische velden (`diagnose`, `icd10`) en geen toegang tot
Wajong of WIA. Bankrekening- en IBAN-velden zie je **wel**, maar uitsluitend
voor het doel "handhaving".

---

## 2. Inloggen, MFA & applicaties

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
| `silver` | `ww` | WW-aanvragen, betalingen, status-historie | **Ja** |
| `gold` | `uc03_ww_risk` | Risico-indicatoren per dossier | **Ja** |
| `silver` | `wia`, `wajong`, `crm` | Andere domeinen | **Nee** |
| `sensitive` | `wajong.*` | Bijzondere persoonsgegevens | **Nee** |

### 3.2 Welke kolommen zie je?

Voor `silver.ww.*` en `gold.uc03_ww_risk.*`:

| Kolom | Wat zie je? | Bijzonderheid |
|---|---|---|
| `bsn`, naam, geboortedatum, adres | **Volledig** | Doel "handhaving" |
| `iban`, `bankrekening` | **Volledig** | Uniek voor jouw rol — anderen zien `NL**********1234` |
| `diagnose`, `icd10` | **Niet** (kolom-mask returnt NULL) | Medisch is niet jouw doel |
| `regio` | Geen filter — landelijk | Handhaving is niet regio-gebonden |

### 3.3 Voorbeeld — onderscheid met andere rollen

Op `silver.persoon.persoon` zien:

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

### 4.2 Workflow B — Onderzoek op één dossier

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
FROM silver.ww.aanvraag a
LEFT JOIN silver.ww.betaling b USING (bsn)
LEFT JOIN gold.uc03_ww_risk.score r USING (bsn)
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
FROM gold.uc03_ww_risk.actuele_signalen
WHERE status = 'in_onderzoek'
GROUP BY team_handhaver
ORDER BY aantal_open DESC;
```

### 4.4 Workflow D — Onderzoeksdossier samenstellen

**Scenario.** Je hebt voldoende signaal voor formeel onderzoek; je wilt een gestructureerd dossier.

1. Maak een nieuwe **Saved Query** in Superset met de joins van workflow B
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
FROM gold.uc03_ww_risk.score
WHERE score_datum >= CURRENT_DATE - INTERVAL '90' DAY
GROUP BY 1
ORDER BY 1;
```

---

## 5. Hulp, fouten & escalatie

### 5.1 Veelvoorkomende foutmeldingen

| Foutmelding | Wat betekent het? | Wat doe je? |
|---|---|---|
| `Access Denied: column 'diagnose' returns NULL` | Medische velden zijn voor jou gemaskeerd | Niet nodig voor handhaving |
| `Access Denied: silver.wia.*` | WIA is niet jouw doel | Vraag een Claims Analyst voor cross-domein vragen |
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
| Inloggen, MFA | Platform-admin |
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

---


## Handleiding — Claims Analyst

> Rol-key: `claims_analyst` · Domein: AG / Wajong · Risiconiveau toegang: zeer hoog (Sensitive Vault, art. 9 AVG)

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

Accountnaam `case.manager`. **MFA verplicht** + extra waarschuwing
in de Keycloak-login: "Je hebt toegang tot de Sensitive Vault. Elke query wordt
gelogd en periodiek gereviewd."

### 2.2 Welke applicaties?

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Dashboards: caseload, trajecten | https://superset.odap.local:8443 |
| **OpenMetadata** | Begrippen, glossary, lineage | https://openmetadata.odap.local:8443 |

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
| `Access Denied: silver.wia.*` | WIA-domein niet toegankelijk | Vraag Claims Analyst |
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

**Vorige:** [02-fraud-analyst.md](02-fraud-analyst.md) ·
**Volgende:** [04-marketing-analyst.md](04-marketing-analyst.md) ·
**Index:** [README.md](README.md)

---


## Handleiding — Marketing Analyst

> Rol-key: `marketing_analyst` · Domein: Klantcontact · Risiconiveau toegang: middel (PII gemaskeerd, geen medisch)

Deze handleiding is voor **medewerkers van klantcontact en CRM**. Je werkt
met het 360°-cliëntbeeld (UC-05) en helpt cliënten via telefoon, balie of
Werkmap. Je ziet **gemaskeerde BSN's** en **geen medische gegevens** —
beide bewust beperkt om dataminimalisatie te respecteren.

---

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
| `gold` | `uc05_client_360` | 360°-cliëntbeeld | **Ja** |
| `silver` | `crm` | Klantcontact-historie | **Indirect** (alleen via UC-05) |
| `silver` | `wia`, `ww`, `wajong` | Domein-data | **Nee** |
| `sensitive` | * | (geen) | **Nee** |

### 3.2 Welke kolommen?

In `gold.uc05_client_360.client_overview`:

| Kolom | Wat zie je? |
|---|---|
| `bsn` | **GEMASKEERD** — `'XXXXXXX' || substring(bsn, 8)` (laatste 2 cijfers zichtbaar) |
| `voornaam`, `achternaam` | Volledig — voor herkenning aan de telefoon |
| `geboortedatum` | Volledig — voor identificatie |
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

1. Vraag haar geboortedatum + de laatste 2 cijfers van haar BSN voor identificatie.
2. Open **Superset → dashboard "Cliënt 360°"**, zoek op gemaskeerde BSN of geboortedatum + naam.
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
FROM gold.uc05_client_360.kanaalwijzigingen
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
FROM gold.uc05_client_360.contact_log
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
| `bsn = NULL` of "uitgegrijsd" | Kolom gemaskeerd, niet gewist | Voor klantidentificatie volstaat naam + geboortedatum |
| `Access Denied: silver.wia.*` | Andere domeinen niet zichtbaar | Verwijs cliënt door naar WIA-team |
| `Cliënt niet gevonden` | Mogelijk synthesedata-mismatch (referentie-omgeving) | Check spelling, gebruik geboortedatum |

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

---


## Handleiding — Finance Analyst

> Rol-key: `finance_analyst` · Domein: Financiën / Beleid · Risiconiveau toegang: laag (alleen aggregaten, geen PII)

Deze handleiding is voor **financieel-economische analisten** die werken
aan schadelast, prognoses en beleidsanalyses. Je werkt op **geaggregeerde
data**: geen ruwe BSN, geen individuele uitkeringsbedragen.

---

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

---


## Handleiding — Operations Manager

> Rol-key: `operations_manager` · Domein: Sociaal-medische zaken · Risiconiveau toegang: laag (geen cliënt-PII)

Deze handleiding is voor **planners die SMZ-capaciteit beheren**:
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

## 2. Inloggen, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Superset** | Capaciteits-dashboards | https://superset.odap.local:8443 |
| **OpenMetadata** | Definities | https://openmetadata.odap.local:8443 |

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs en schemas

| Catalog | Schema | Inhoud | Toegang |
|---|---|---|---|
| `gold` | `uc08_smz_capaciteit` | Capaciteits-aggregaten | **Ja** |
| `silver` | `smz` | SMZ-rooster en case-counts | **Ja** |
| `silver` | `wia`, `ww`, `wajong`, `crm` | Cliënt-dossiers | **Nee** |
| `sensitive` | * | (geen) | **Nee** |

### 3.2 Welke kolommen?

In `gold.uc08_smz_capaciteit.*` en `silver.smz.*`:

| Kolom | Wat zie je? |
|---|---|
| `beoordelaar_id` | Pseudoniem (geen naam) |
| `team`, `regio`, `specialisme` | Volledig — voor planning |
| `rooster_uren` | Volledig |
| `caseload_aantal` | Aggregaat-aantal |
| `wachttijd_dagen` | Mediane/gem. wachttijd |
| `bsn`, naam, diagnose, etc. | NULL (kolom-mask) — geen cliënt-PII |
| `doorlooptijd_dagen` (geaggregeerd) | Volledig |

### 3.3 Doelbinding

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
FROM   gold.uc08_smz_capaciteit.wachttijd
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
  FROM   gold.uc08_smz_capaciteit.wachttijd
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
| `Access Denied: silver.wia.aanvraag` | Cliënt-data niet voor planning | Werk op aggregaat-mart |
| `bsn IS NULL` | Kolom gemaskeerd | Niet nodig voor planning |

| Probleem | Contact |
|---|---|
| Inloggen | Platform-admin |
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

---


## Handleiding — Marketing Analyst

> Rol-key: `marketing_analyst` · Domein: Toeslagenwet (proactief) · Risiconiveau toegang: middel (PII, geen medisch)

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
| **Apache Superset** | Werklijst-dashboard | https://superset.odap.local:8443 |
| **OpenMetadata** | Definities, model-info | https://openmetadata.odap.local:8443 |

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

**Vorige:** [06-operations-manager.md](06-operations-manager.md) ·
**Volgende:** [08-researcher.md](08-researcher.md) ·
**Index:** [README.md](README.md)

---


## Handleiding — Researcher

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
| **Apache Superset** | Dashboards en SQL Lab | https://superset.odap.local:8443 |
| **OpenMetadata** | Definities, lineage van panels | https://openmetadata.odap.local:8443 |

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

---


## Handleiding — Data-steward

> Rol-key: `data_steward` · Domein: Datakwaliteit & governance · Risiconiveau toegang: hoog (PII voor DQ-controle)

Deze handleiding is voor **data-stewards**. Jij bent de spil tussen
data-engineers (die pipelines bouwen) en eindgebruikers (die data
gebruiken). Je zorgt voor kwaliteit, lineage, eigenaarschap en juiste
classificatie. Je ziet PII voor controledoeleinden, **niet** medische data.

---

## 1. Wat doet jouw rol?

Je bewaakt de governance van het platform. Je gebruikt het platform om:

- Datakwaliteit te bewaken (dbt-tests, OpenMetadata-profiler)
- Eigenaarschap, classificaties en doelbindingen actueel te houden
- Lineage te valideren (van bron tot dashboard)
- Glossary (CGM-begrippen) te onderhouden
- Sensitive-queries van Claims Analystn te reviewen
- Eindgebruikers te helpen bij begrip en interpretatie van data

---

## 2. Inloggen, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **OpenMetadata** | Hoofdwerkplek: catalog, glossary, classificaties, profiler, lineage | https://openmetadata.odap.local:8443 |
| **Apache Superset** | Dashboards reviewen, ownership-overzichten | https://superset.odap.local:8443 |
| **Apache Airflow** | DQ-DAGs draaien | https://airflow.odap.local:8443 |
| **OpenSearch (Kibana-achtig)** | OPA-decision-logs reviewen | https://opensearch.odap.local:8443/logs |
| **dbt CLI / docs** | dbt-tests + lineage-docs | lokaal of via VS Code remote |

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs

| Catalog | Toegang | Doel |
|---|---|---|
| `bronze` | **Ja** (kwaliteitscontrole) | Vergelijken bron met silver |
| `silver` | **Ja** | DQ-bewaking, profiler |
| `gold` | **Ja** | Validatie van marts |
| `sensitive` | **Nee** | Niet jouw doel — alleen Claims Analystn + admin |
| `sandbox` | **Nee** | Researcher-zone |

### 3.2 Welke kolommen?

PII (BSN, naam, IBAN) zie je **volledig** voor DQ-controle. Medisch
(`diagnose`, `icd10`) zie je **niet** — daarvoor heb je geen doel.

> **Vuistregel.** Je hebt PII-toegang om datakwaliteit te valideren, niet om
> dossiers te lezen. Steekproeven, niet bulk-exports.

### 3.3 Doelbindingen

Purposes: **"sturingsinfo"** en **"kwaliteitscontrole"**. Sommige
doel-specifieke marts (UC-04, UC-05) zijn voor jou alleen vanuit
kwaliteitscontrole-perspectief beschikbaar.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Dagstart: DQ-overzicht

1. Open **OpenMetadata** → **Quality** → **Test Suites**.
2. Bekijk welke dbt-tests vannacht faalden (rood).
3. Per fout: klik door naar de testbeschrijving + de records die faalden.

Of via Trino:

```sql
SELECT
  test_name,
  failures,
  last_run
FROM   gold.uc07_dq_polisadm.test_resultaten_daily
WHERE  status = 'failed'
ORDER  BY last_run DESC;
```

### 4.2 Workflow B — Profiler-vlag uitzoeken

**Scenario.** OpenMetadata toont rood vlag op `silver.wia.aanvraag.regio`:
"5% NULL, vorige week 0.2%". Je gaat onderzoeken.

```sql
-- Hoeveel NULL?
SELECT
  date_trunc('day', aanvraag_datum) AS dag,
  100.0 * SUM(CASE WHEN regio IS NULL THEN 1 ELSE 0 END) / COUNT(*) AS null_pct
FROM   silver.wia.aanvraag
WHERE  aanvraag_datum >= CURRENT_DATE - INTERVAL '14' DAY
GROUP  BY 1
ORDER  BY 1;
```

Vermoeden: ingestion-issue. Je escaleert naar de data-engineer.

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
3. Koppel de term aan `silver.wia.voorschot.bedrag`.
4. Communiceer naar gebruikers (e-mail of dashboard-update).

### 4.6 Workflow F — Lineage valideren

```sql
-- Welke marts hangen van silver.wia.aanvraag?
SELECT downstream_table
FROM   metadata.lineage
WHERE  upstream_table = 'silver.wia.aanvraag';
```

Of in OpenMetadata: klik **Lineage** op `silver.wia.aanvraag` en zie alle
downstream-marts en dashboards.

### 4.7 Workflow G — DPIA-evidence verzamelen

Voor periodieke audits exporteer je:

- OPA-test-resultaten (`make opa-test`, 23/23 PASS)
- OpenMetadata classifications-export
- dbt-test-history van de laatste 30 dagen
- Decision-log statistieken

Zie [`docs/runbook.md` § 10](../runbook.md) voor de volledige procedure.

---

## 5. Verantwoordelijkheden in volgorde van prioriteit

1. **Kwaliteit van productie-zones** (silver/gold) — fouten hier raken besluiten.
2. **Sensitive-review** — dagelijks, 1e taak van de ochtend.
3. **Eigenaarschap-coverage** — > 95% van datasets moet een eigenaar hebben.
4. **DPIA-evidence** — actueel en toegankelijk voor toezichthouders.
5. **Glossary-onderhoud** — gebruikers moeten begrippen kunnen vinden.

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

---


## Handleiding — Data-engineer

> Rol-key: `data_engineer` · Domein: Data-pipelines & ingestion · Risiconiveau toegang: hoog (PII in bronze, JIT)

Deze handleiding is voor **data-engineers** die pipelines bouwen en
beheren. Je hebt **JIT-toegang** (just-in-time) tot `bronze.*` voor
debug-doeleinden — niet voor permanent gebruik. Je bouwt NiFi-flows,
Spark-jobs, dbt-modellen en Airflow-DAGs.

---

## 1. Wat doet jouw rol?

Je bouwt en onderhoudt de datastromen van bron tot mart. Je gebruikt het
platform om:

- Brondata via NiFi naar Kafka te krijgen
- Spark Structured Streaming jobs te draaien (Kafka → Delta op MinIO)
- dbt-modellen te bouwen (`silver.*` → `gold.*`)
- Airflow-DAGs voor batch en onderhoud te schedulen
- DQ-tests in te bouwen
- Bronze-data te debuggen wanneer nodig

---

## 2. Inloggen, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Airflow** | DAGs maken, runs monitoren | https://airflow.odap.local:8443 |
| **dbt CLI** | Lokaal of in CI | terminal |
| **kubectl + k9s** | Spark-jobs, pod-status, Hive Metastore | terminal |
| **Apache Superset** | Eigen build-dashboards reviewen | https://superset.odap.local:8443 |
| **OpenMetadata** | Service-config, lineage publishing | https://openmetadata.odap.local:8443 |
| **MinIO Console** | Bucket-debugging | https://minio.odap.local:8443 |

- NiFi-flows worden as-code beheerd in `nifi-flows/templates/` en geïmporteerd via `kubectl port-forward` (zie `nifi-flows/templates/delta/README.md`).
- dbt en Airflow benaderen Trino in-cluster; voor ad-hoc debug: `kubectl -n odap-platform port-forward svc/trino-coordinator 8443:8443`.

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs

| Catalog | Toegang | Hoe? |
|---|---|---|
| `bronze` | **JIT** — moet aanvragen | Via Trino, alleen na ticket-id in PR/PR-comment |
| `silver`, `gold` | **Indirect** — via dbt-runs en CI | Niet direct queryen voor business-doel |
| `sensitive`, `sandbox` | **Nee** | Alleen domein-rollen / researcher |

### 3.2 JIT-procedure

1. Ticket aanmaken in tracker (Linear/Jira) met **doel** en **scope**.
2. Platform-admin keurt goed; rol wordt 4 uur geactiveerd voor jouw account.
3. Jouw queries worden gelogd. Na 4 uur deactiveert toegang automatisch.
4. Voeg ticket-id toe als comment bij elke query (`-- TICKET-1234`).

### 3.3 Welke kolommen?

In `bronze.uwv.*`: alles ruw — inclusief BSN, naam, IBAN. Wees uiterst
zuinig: **kijk niet meer dan nodig**.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Nieuwe bron toevoegen

**Scenario.** Beleid vraagt om data van een nieuw bronsysteem `xyz`.

1. **Ontwerp**: schrijf een mini-spec in `docs/use-cases/uc-xyz.md` (entiteiten, classificatie, doelbinding, bewaartermijn).
2. **NiFi-flow**: kopieer template `nifi-flows/templates/delta/source-xyz/` aan, pas processors aan.
3. **Kafka-topic**: definieer `uwv.xyz.event` in `platform/06-kafka/topics.yaml`.
4. **Spark-job**: voeg `streaming-bronze-xyz.yaml` toe; gebruik helper `lakehouse_io.write_delta()`.
5. **Schema in HMS**: `CREATE TABLE bronze.uwv.xyz_events (...) USING DELTA LOCATION 's3a://odap-bronze/xyz/'`.
6. **dbt-stg**: `dbt/models/staging/stg_xyz.sql` met basisvalidatie.
7. **OPA-update**: voeg purpose toe in `data/role_mappings.json::resource_purposes`.
8. **OpenMetadata**: voeg service-config toe (auto-discovery).
9. **CI**: `make opa-test`, `dbt parse`, smoke tests.
10. **PR review** door data-steward + platform-admin.

### 4.2 Workflow B — dbt-model maken

```sql
-- dbt/models/marts/uc_xyz/mart_xyz_daily.sql
{{ config(
    materialized = 'table',
    table_format = table_format_properties()['table_format']
) }}

WITH src AS (
    SELECT * FROM {{ ref('stg_xyz') }}
)
SELECT
    date_trunc('day', event_ts) AS dag,
    COUNT(*)                    AS aantal,
    AVG(value)                  AS gem_value
FROM src
GROUP BY 1
```

Met `schema.yml`:

```yaml
version: 2
models:
  - name: mart_xyz_daily
    meta:
      eigenaar: data.steward@odap.local:8443
      domain: xyz
      legal_basis: art_6_1e
      doelbinding: [sturingsinfo]
      bewaartermijn_jaren: 7
      pii_kolommen: []
    columns:
      - name: dag
        tests: [not_null]
      - name: aantal
        tests: [not_null]
```

Run: `dbt run --select mart_xyz_daily && dbt test --select mart_xyz_daily`.

### 4.3 Workflow C — Streaming-job debuggen

**Scenario.** Spark-job hangt in `streaming-bronze-wia`.

1. `kubectl get sparkapp -n odap-platform`
2. `kubectl logs -n odap-platform <driver-pod>`
3. Spark UI port-forwarden:
   ```
   kubectl port-forward -n odap-platform svc/spark-streaming-ui 4040:4040
   ```
   Open http://localhost:4040
4. Checkpoint-bucket inspecteren via MinIO Console: `s3://odap-checkpoints/<job>/`
5. Zie [`docs/runbook.md` § 4.3](../runbook.md) voor scenario-stappen.

### 4.4 Workflow D — Pipeline-falen patchen

```bash
## Lokaal testen
make doctor                       # cluster-health
dbt parse --target dev
dbt build --select +mart_failed   # bouw upstream tot en met deze

# Naar cluster
kubectl apply -f platform/08-spark/apps/streaming-bronze-fixed.yaml
```

### 4.5 Workflow E — Onderhoud-DAG (compaction/vacuum)

Airflow-DAG `lakehouse_maintenance` draait dagelijks. Format-aware:

- Delta: `OPTIMIZE` + `VACUUM`
- Iceberg: `expire_snapshots` + `rewrite_data_files`

Bij falen: bekijk de Airflow-task-log; meestal is het MinIO disk-druk of
Hive-metastore lock.

### 4.6 Workflow F — JIT-aanvraag voor bronze

Stel: een dbt-test faalt met `IBAN format invalid`. Je wilt zien hoe de
ruwe IBAN binnenkomt vanuit bronze.

1. Open ticket: "TICKET-1234: debug iban-validatie WIA-aanvraag, bronze toegang 4u"
2. Platform-admin keurt goed
3. Query met ticket-id:
   ```sql
   -- TICKET-1234
   SELECT iban, COUNT(*)
   FROM   bronze.uwv.wia_aanvraag_raw
   WHERE  ingest_dag = CURRENT_DATE
   GROUP  BY iban
   LIMIT  20;
   ```
4. Los root-cause op, deploy fix, sluit ticket. Toegang verloopt automatisch.

---

## 5. Code- en deploy-discipline

- **Geen `latest`-tags.** Pin altijd image-versies; release-pinning in `infrastructure/stackablectl/release.yaml`.
- **Geen plaintext secrets.** Gebruik Stackable secret-operator + Vault (productie).
- **Eén ADR per architectuurkeuze.** Zie `docs/adr/` voor format.
- **Format-agnostisch.** Geen hardcoded `delta` of `iceberg` buiten de switch-points (zie [docs/architecture.md § 4](../architecture.md)).
- **CI moet groen.** PR's met rode CI worden niet gereviewd.

---

## 6. Hulp, fouten & escalatie

| Probleem | Contact |
|---|---|
| Cluster down | Platform-admin (telefonisch) |
| OPA-policy verandering | Pair met platform-admin + data-steward |
| Schema-mismatch in bronze | Bron-eigenaar (UWV-zijde) |
| Productie-incident | Volg [`docs/runbook.md` § 4](../runbook.md) |

| Foutmelding | Actie |
|---|---|
| `Hive metastore connection refused` | `kubectl get hivecluster -A`; restart als nodig |
| `dbt test failed: bsn_valid` | Synthetische generator faalt? Of echte ingestion-fout? |
| `OPA bundle out of date` | `scripts/build-opa-bundle.sh && kubectl apply -f platform/10-opa/` |

---

## 7. Wat je nooit doet

- Permanente toegang tot `bronze.*` activeren — JIT, altijd JIT.
- Productie-data downloaden naar je laptop voor lokaal werk.
- Een Spark-job zonder unit-tests in productie deployen.
- Wijzigingen in `platform-config.yaml::table_format` zonder ADR.
- Direct `kubectl edit` op productie-CRDs — alles via PR + GitOps.

---

**Vorige:** [09-data-steward.md](09-data-steward.md) ·
**Volgende:** [11-platform-admin.md](11-platform-admin.md) ·
**Index:** [README.md](README.md)

---


## Handleiding — Platform-admin

> Rol-key: `platform_admin` · Domein: Cluster + security · Risiconiveau toegang: maximaal (break-glass)

Deze handleiding is voor **platform-admins**. Je hebt break-glass-toegang
tot **alle catalogs**, inclusief `sensitive` en `sandbox`. Je rol is **niet
voor day-to-day werk** — je bent er voor incidenten, structurele wijzigingen
en governance van het platform zelf. **Elke break-glass-actie wordt gelogd
en achteraf gereviewd.**

---

## 1. Wat doet jouw rol?

Je bent eindverantwoordelijk voor de werking en veiligheid van het
platform. Je gebruikt het platform om:

- Cluster-incidenten op te lossen
- Toegang en rollen te beheren in Keycloak
- OPA-policies te beoordelen en te deployen
- Backups en restores uit te voeren
- Compliance-evidence te exporteren
- JIT-aanvragen van data-engineers goed te keuren
- Structurele wijzigingen (architectuur, ADR's, security) te begeleiden

---

## 2. Inloggen, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Keycloak Admin** | Rolbeheer, gebruikers, MFA-policies | https://keycloak.odap.local:8443/admin |
| **kubectl + k9s** | Alle clusters, alle pods | terminal |
| **Apache Airflow** | Maintenance-DAGs | https://airflow.odap.local:8443 |
| **OpenSearch / OPA-logs** | Audit-log review | via Vector ingestion |
| **OpenMetadata** | Service-config, governance | https://openmetadata.odap.local:8443 |
| **Prometheus + Grafana** | Metrics, alerts | https://grafana.odap.local:8443 |
| **MinIO Console** | Bucket-beheer | https://minio.odap.local:8443 |

- Trino break-glass queries: `kubectl -n odap-platform port-forward svc/trino-coordinator 8443:8443` en dan via DBeaver op `localhost:8443`.

> **MFA verplicht en hardware-gebonden.** Voor productie: WebAuthn-passkey of
> hardware-token (YubiKey). Geen TOTP-app op een mobiel.

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs

Je hebt toegang tot **alles**: `bronze`, `silver`, `gold`, `sensitive`,
`sandbox`. Toegang valt onder **break-glass**: elke query staat de
volgende ochtend op het reviewscherm van de data-steward.

> **Vuistregel break-glass.** Doe het alleen voor:
> 1. Incident-respons (productie down, data corrupt)
> 2. Compliance-evidence verzamelen
> 3. Onderhouds-validatie (niet voor begripsmatige queries)
>
> Voor "ik wilde even kijken" gebruik je een eigen non-admin account.

### 3.2 Audit-discipline

Elke break-glass-query begint met een comment:

```sql
-- BREAK-GLASS REASON: incident INC-2026-04-30 / cliënt 999000123 / data corruptie review
SELECT ... FROM sensitive.wajong.dossier WHERE bsn = '999000123';
```

De data-steward valideert de volgende ochtend dat deze comments er zijn.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Cluster-health checken

```bash
## Snelste overview
make doctor

# Per Stackable-laag
kubectl get pods -n odap-platform
kubectl get pods -n odap-data
kubectl get pods -n odap-meta
kubectl get pods -n odap-monitoring
kubectl get pods -n odap-auth

# Custom resources
kubectl get trinocluster,kafkacluster,hivecluster,opacluster,airflowcluster,supersetcluster,nificluster -A
```

### 4.2 Workflow B — Nieuwe gebruiker toevoegen

> In productie: gebeurt via SSO-federatie (DigiD/eHerkenning of Entra ID).
> In deze referentie via Keycloak Admin.

1. Open https://keycloak.odap.local:8443/admin → realm `uwv` → **Users → Add user**.
2. Vul username, email, voornaam, achternaam.
3. Tab **Credentials** → temporary password.
4. Tab **Role mappings** → wijs de juiste rol toe (één rol per persoon!).
5. Stuur de gebruiker zijn login-link + verzoek MFA in te stellen bij eerste login.

### 4.3 Workflow C — JIT-aanvraag goedkeuren

1. Data-engineer maakt ticket "TICKET-1234: bronze access 4u, doel debug iban".
2. Lees doel + scope. Bij twijfel: bel de data-engineer voor toelichting.
3. Activeer rol via Keycloak (4 uur). In productie: dit gaat via een
   automatiseringsscript dat de mapping in OPA tijdelijk aanpast.
4. Sluit het ticket met je goedkeuring; markeer in audit-log waarom.

### 4.4 Workflow D — OPA-policy deployen

Wijzigingen aan policies gebeuren in `opa-policies-src/`. Process:

```bash
# 1. Test lokaal
make opa-test                     # 23/23 PASS verwacht

# 2. Build bundle
scripts/build-opa-bundle.sh       # rendert ConfigMap

# 3. Deploy
kubectl apply -f platform/10-opa/

# 4. Verifieer
kubectl logs -n odap-platform <opa-pod>
# en draai smoke test:
tests/smoke/08-opa-decisions.sh
```

> **Pair-review verplicht.** OPA-policies krijgen altijd een tweede paar ogen
> (data-steward of senior platform-engineer) vóór deploy.

### 4.5 Workflow E — Backup uitvoeren

Volgens [`docs/runbook.md` § 5](../runbook.md):

```bash
# MinIO mirror
mc mirror local/odap-bronze backup-bucket/odap-bronze/$(date -I)/
mc mirror local/odap-silver backup-bucket/odap-silver/$(date -I)/
mc mirror local/odap-gold backup-bucket/odap-gold/$(date -I)/
mc mirror local/sensitive backup-bucket/sensitive/$(date -I)/

# Postgres dumps (Hive Metastore, Airflow, Superset, OpenMetadata)
for db in hive airflow superset openmetadata; do
  kubectl exec -n odap-platform postgres-$db-0 -- \
    pg_dump -U $db $db > backups/$db-$(date -I).sql
done

# Keycloak realm export
kubectl exec -n odap-auth keycloak-0 -- \
  /opt/keycloak/bin/kc.sh export --file /tmp/odap-realm.json --realm uwv
kubectl cp odap-auth/keycloak-0:/tmp/odap-realm.json backups/odap-realm-$(date -I).json
```

### 4.6 Workflow F — Incident-response (cluster down)

Volgens [`docs/runbook.md` § 4](../runbook.md):

1. **Triage**: `make doctor`, lees recente alerts in Grafana.
2. **Communicatie**: meld incident in Slack `#incidents`; zet status-page.
3. **Stabilize**: rolling restart van het falende component (`kubectl rollout restart`).
4. **Diagnose**: pod-logs, OPA-decision-log, OpenSearch.
5. **Resolve**: pas patch toe; als infra-niveau, escaleer naar SRE.
6. **Post-mortem**: schrijf binnen 48u een incident-rapport (geen schuldvinger).

### 4.7 Workflow G — Compliance-evidence exporteren

Voor een audit:

```bash
# OPA-tests
make opa-test > evidence/opa-test-$(date -I).log

# OpenMetadata classifications
curl -H "Authorization: Bearer $TOKEN" \
  https://openmetadata.odap.local:8443/api/v1/tags?fields=classifications \
  > evidence/om-classifications-$(date -I).json

# dbt test history
dbt run --select metadata.dbt_test_results > evidence/dbt-tests-$(date -I).log

# OPA decision-log statistieken
opensearch-curl /logs-*/_search?q=opa.decision&size=0&_source=false \
  > evidence/opa-decisions-stats-$(date -I).json
```

Zie [`docs/runbook.md` § 10](../runbook.md) voor volledige procedure.

### 4.8 Workflow H — NIS2-meldplicht 24u/72u

Bij ernstig incident:

1. **Binnen 24u**: vroegsignalering bij Nationaal Cyber Security Centrum (NCSC).
2. **Binnen 72u**: officieel incident-rapport met scope, oorzaak, impact, mitigatie.
3. **Binnen 1 maand**: definitief evaluatierapport.

Templates en escalatie-paden: out-of-platform via Platform CISO.

---

## 5. Verantwoordelijkheden

In volgorde van prioriteit:

1. **Beschikbaarheid en integriteit** van het platform.
2. **Toegangs-discipline**: alleen wie het nodig heeft, alleen wat nodig is.
3. **Incident-respons**: snel, gestructureerd, navolgbaar.
4. **Backup en restore**: getest, niet alleen "ingericht".
5. **Compliance-evidence**: actueel, exporteerbaar.
6. **Beleidshygiëne**: ADR's, runbook, dependency-pinning.

---

## 6. Hulp, fouten & escalatie

| Probleem | Contact |
|---|---|
| Productie-incident | Volg runbook + UWV SRE-team |
| Beleidsvraag | Platform CISO + Data Office |
| Wettelijke vraag | Privacy Officer (FG) |
| Burnout / overbelasting | Manager + collega-admin (rol moet redundant zijn!) |

---

## 7. Wat je nooit doet

- Break-glass-toegang gebruiken voor "snelle vragen" — maak een non-admin account.
- Een productie-OPA-policy patchen zonder PR + tweede paar ogen.
- Direct `kubectl edit` op productie-CRDs — altijd via GitOps.
- Een wachtwoord in plaintext doorsturen, ook niet "tijdelijk".
- MFA disable-en voor "even debuggen".
- Nieuwe rollen creëren zonder vermelding in `role_mappings.json` + ADR.

---

**Vorige:** [10-data-engineer.md](10-data-engineer.md) ·
**Volgende:** [12-smoketest-systeem.md](12-smoketest-systeem.md) ·
**Index:** [README.md](README.md)

---


## Handleiding — Smoketest (systeemrol)

> Rol-key: `smoketest` · Type: **service-account, geen mens** · Risiconiveau toegang: middel

Dit is **geen rol voor mensen**. Het is een service-account voor
geautomatiseerde tests, dbt-runs in CI en smoke tests bij deploy.
Deze handleiding is voor de **platform-admins en data-engineers** die
deze rol configureren en bewaken.

---

## 1. Waar wordt deze rol gebruikt?

- **CI-pipeline** (`ci/github-actions/`) — bij elke PR run je `dbt parse`, `opa test`, smoke tests.
- **Smoke tests** (`scripts/run-smoke-tests.sh`, `tests/smoke/*.sh`) — verifiëren dat het cluster werkt.
- **dbt-runs** in Airflow voor `staging`/`marts` — non-interactief.
- **Geen interactieve gebruikers** — login geweigerd, alleen service-account-flow.

---

## 2. Hoe is deze rol opgezet?

### 2.1 In OPA

```json
"smoketest": {
  "_role_purpose": "Static-auth user voor smoke-tests + dbt-runs.",
  "catalogs": ["bronze", "silver", "gold"],
  "schemas": null,
  "purposes": ["*"],
  "can_see_pii": true,
  "can_see_medical": false,
  "can_see_bankrekening": false,
  "regio_filter": false,
  "break_glass": false
}
```

> **Waarom alle purposes (`*`)?** Smoke tests valideren dat queries
> *technisch* werken. De purposes zijn niet bedoeld als doelbinding maar
> als test-coverage. In productie wordt deze rol **alleen vanuit de CI**
> aangesproken, niet vanaf werkstations.

### 2.2 Authenticatie

Geen password-flow. Het service-account gebruikt:

- **Static OIDC client credentials** (Keycloak `client_credentials`-grant)
- Secret in `Stackable secret-operator` (productie: External Secrets + Vault)

### 2.3 Geen sensitive

`smoketest` heeft **geen** toegang tot `sensitive.*` of `sandbox.*`.

---

## 3. Wat doet deze rol concreet?

### 3.1 dbt-runs

```bash
## In Airflow-DAG of CI
dbt run --target prod --profiles-dir /etc/dbt/profiles
dbt test --target prod
```

Het `profiles.yml` haalt credentials uit env-vars (mounted via secret-operator).

### 3.2 Smoke tests

```bash
# tests/smoke/01-trino-up.sh
trino --user smoketest --catalog gold --execute "SELECT 1"

# tests/smoke/05-dbt-runs.sh
dbt build --select +mart_uc01_wia_funnel_daily

# tests/smoke/08-opa-decisions.sh
# verifieert dat OPA accept/deny correct werkt
```

### 3.3 Synthetische data laden

```bash
# data-generation/seed.py via Airflow seed-DAG
python -m data_generation.seed --rows 10000 --user smoketest
```

---

## 4. Bewaking

### 4.1 Wat moet je monitoren?

| Metric | Verwacht | Alert-threshold |
|---|---|---|
| `smoketest` queries per uur | < 200 | > 500 = mogelijk runaway-job |
| `smoketest` access tot `silver/wia/aanvraag` | dagelijks 1-5x | > 50/dag = pipeline-loop |
| Failed auth voor `smoketest` | 0 | > 0 = secret-rotation issue |
| Decision-log entries `smoketest` op `gold.*` | normaal | sudden spike = onderzoeken |

Alerts gaan via Prometheus → AlertManager → Slack `#platform-alerts`.

### 4.2 Periodieke review

Maandelijks (data-steward + platform-admin):

1. Bekijk OPA decision-log voor `smoketest` op productie-zones.
2. Controleer of er **geen** queries zijn met cliënt-specifieke filters
   (`WHERE bsn = '...'`) — dat zou betekenen dat een mens deze rol misbruikt.
3. Verifieer dat secret-rotatie afgelopen periode is uitgevoerd.

---

## 5. Wat te doen bij anomalieën?

### 5.1 Onverwachte spike in smoke-queries

1. Check Airflow voor lopende DAGs — vermoedelijk een retry-loop.
2. Pauzeer de DAG.
3. Onderzoek de fout.
4. Hervat na fix.

### 5.2 `smoketest` doet plotseling sensitive-queries

Dit is **niet** mogelijk volgens OPA-policy: deny default. Als toch:

1. **Direct** smoke-test deactiveren in Keycloak.
2. Onderzoek hoe een sensitive-query überhaupt door OPA kwam.
3. Audit-log van laatste 24u exporteren.
4. Incident melden volgens NIS2-procedure (zie [11-platform-admin.md](11-platform-admin.md) § 4.8).

### 5.3 Failed auth — secret rotation

Als CI-runs failen met `401 Unauthorized` voor `smoketest`:

1. Secret is verlopen of geroteerd zonder propagatie.
2. Vernieuw via secret-operator:
   ```bash
   kubectl annotate secret smoketest-oidc-secret -n odap-platform \
     stackable.tech/refresh=$(date +%s)
   ```
3. Restart de DAG / smoke-test.

---

## 6. Beveiligingsregels

- **Geen interactief gebruik.** Login als `smoketest` vanaf een werkstation
  is technisch geblokkeerd (geen direct grant).
- **Geen gedeeld secret.** Het OIDC-client-secret komt alleen uit de
  secret-operator; staat **niet** in code, niet in env-files, niet in chats.
- **Roteer per kwartaal** (productie). In dev: bij elke fresh `make bootstrap`.
- **Audit-log = bewijs.** Bij twijfel over wat de rol gedaan heeft, lees
  de log; vraag het niet aan de developers.

---

## 7. Wat je nooit doet

- `smoketest`-credentials gebruiken voor "snel een query" — gebruik je eigen account.
- `smoketest` extra rechten geven om een test te laten slagen — fix de test.
- Een productie-DAG schrijven die `smoketest` als impersonatie van een mens-rol gebruikt.

---

**Vorige:** [11-platform-admin.md](11-platform-admin.md) ·
**Index:** [README.md](README.md)

---
