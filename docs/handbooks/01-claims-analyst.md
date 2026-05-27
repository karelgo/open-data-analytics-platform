# Handleiding — Claims Analyst

> Rol-key: `claims_analyst` · Domein: AG / WIA · Risiconiveau toegang: hoog (PII + medisch)

Deze handleiding is voor **verzekeringsartsen, arbeidsdeskundigen en
beoordelaars** die WIA-aanvragen behandelen. Je gebruikt het platform om
dossiers te raadplegen, voorraad en doorlooptijden in jouw regio te bewaken
en sturingsinformatie op te vragen.

---

--8<-- "_snippets/url-modes.md"

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
| `gold` | `uc01_claims_funnel` | Sturingsmart: voorraad, doorlooptijden, voorspelling | **Ja** |
| `silver` | `ww`, `wajong`, `crm`, ... | Andere domeinen | **Nee** |
| `sensitive` | `wajong.*` | Sociaal-medisch dossier Wajong | **Nee** |
| `bronze` | alles | Ruwe brondata | **Nee** |

### 3.2 Welke kolommen zie je?

Voor `silver.claims.application` en `gold.uc01_claims_funnel.*`:

| Kolom | Wat zie je? | Waarom? |
|---|---|---|
| `bsn` | **Volledig** | Je hebt PII-doel "uitkering/behandeling/reintegratie" |
| `voornaam`, `achternaam` | Volledig | Idem |
| `birth_date` | Volledig | Idem |
| `straat`, `huisnummer` | Volledig | Idem |
| `iban`, `bankrekening` | **GEMASKEERD** (bv. `NL**********1234`) | Jij beoordeelt geen betalingen — die staat bij FEZ |
| `diagnose`, `icd10` | Volledig (alleen voor je eigen regio) | Medisch noodzakelijk voor WIA-beoordeling |
| `regio` | Filter — **alleen jouw regio's** | Doelbinding regio-gebonden |

> **Rij-filter (regio_filter).** Het platform past automatisch een rij-filter toe:
> `WHERE regio IN (jouw toegewezen regio's)`. Je hoeft dit niet zelf te schrijven.
> Een query op heel Nederland levert alleen jouw regio op — geen foutmelding.

### 3.3 Wat zie je echt **niet**?

- WW-data (`silver.service_requests.*`) — andere doelbinding (handhaving, niet WIA)
- Wajong sensitive (`sensitive.eligibility_cases.*`) — alleen Claims Analystn
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
  birth_date,
  aanvraag_datum,
  status,
  diagnose,
  regio
FROM silver.claims.application
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
FROM gold.uc01_claims_funnel.afgehandeld
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
2. Zoek op `mart_uc01_claims_funnel_daily` of op kolomnaam
3. Bij elke kolom zie je: **definitie**, **eigenaar** (data-steward), **bron-tabel**,
   **bewaartermijn**, **classificatie**
4. Klik **Lineage** om de keten van bron → mart te zien

---

## 5. Veelgebruikte queries (kort)

```sql
-- Aantal aanvragen per status, jouw regio's automatisch
SELECT status, COUNT(*) FROM silver.claims.application GROUP BY status;

-- Dossiers > 8 weken open
SELECT bsn, aanvraag_datum, status
FROM   silver.claims.application
WHERE  status = 'open'
  AND  aanvraag_datum < CURRENT_DATE - INTERVAL '56' DAY;

-- Top-10 ICD-10 categorieën
SELECT icd10, COUNT(*) AS n
FROM   silver.claims.beoordeling
GROUP  BY icd10
ORDER  BY n DESC LIMIT 10;
```

---

## 6. Hulp, fouten & escalatie

### 6.1 Veelvoorkomende foutmeldingen

| Foutmelding | Wat betekent het? | Wat doe je? |
|---|---|---|
| `Access Denied: cannot select from gold.uc02_complex_cases.*` | Je probeert Wajong te lezen — niet jouw rol | Niets — vraag een Claims Analyst |
| `Access Denied: regio = 'Zuid' niet toegestaan` | Je rij-filter blokkeert dit, BSN valt buiten je regio | Vraag een collega in de juiste regio |
| `Access Denied: column 'iban' is masked` | Je probeert IBAN onmasked te zien — niet voor WIA | Leef met de mask, of vraag FEZ |
| `Authentication failed: token expired` | OIDC-token is verlopen | Log opnieuw in via Keycloak |
| `Error: schema 'claims' not found` | Trino-catalog niet bereikbaar | Vraag platform-admin (zie 6.3) |

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
