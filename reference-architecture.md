# Referentiearchitectuur — Open Data & Analytics Platform

**Versie:** 1.0 (fictief, ter illustratie)
**Scope:** een doelarchitectuur voor het UWV-brede data- en analyticsplatform, aansluitend op de **Waardegedreven Data & Analytics Strategie (WDAS)**, het **Canoniek Gegevensmodel (CGM)**, **Dmap** en de SUWI-ketenarchitectuur (**KARWEI**), compliant met **NORA, AVG, BIO/BIO2, NIS2 en de AI Act**.
**Disclaimer:** dit document gebruikt fictieve use cases en illustratieve technologiekeuzes. Echte UWV-implementaties wijken af.

---

## Inhoudsopgave

1. Managementsamenvatting
2. Context en kaders
3. Wettelijk kader en datadomeinen
4. Architectuurprincipes
5. Conceptuele referentiearchitectuur
6. Logische bouwblokken per laag
7. Cross-cutting capabilities
8. Fictieve use cases (uitgewerkt)
9. Technologiekeuzes (illustratief)
10. Compliance-mapping
11. Migratie en roadmap
12. Risico's en aandachtspunten

---

## 1. Managementsamenvatting

UWV verwerkt persoonsgegevens van ruim 13,8 miljoen mensen (polisadministratie), voert wettelijke taken uit voor WW, WIA, Wajong, ZW, WAO, WAZ, Wazo, TW en IOW, en is via **BKWI** centrale broker voor de SUWI-keten. Het huidige landschap kent veel legacy (deels OpenVMS), gefragmenteerde BI (SQL Server stack, Power BI) en een groeiend Advanced Analytics-platform (**Dmap**). De WDAS-routekaart zet in op één moderne, schaalbare voorziening waarin **datakwaliteit, hergebruik, transparantie en ethiek** centraal staan.

Deze referentiearchitectuur beschrijft een **lakehouse-gebaseerd data- en analyticsplatform** met:

- een **medallion-architectuur** (bronze/silver/gold) bovenop een open tabelformaat (Iceberg/Delta);
- strikte **doelbinding en zone-scheiding** (bron-, geanonimiseerde-, en use-case-zones);
- een **data mesh-georiënteerde** organisatie met gefedereerde data products per domein (WW, AG, AKO, FEZ, Handhaving, etc.) en centrale governance via Data Office;
- volledige **lineage tot CGM/FUGEM**;
- een **AI-governance-laag** met algoritmeregister, MRM-beleid en AI Act-classificatie;
- verzwaarde maatregelen voor **AVG, BIO2 en NIS2** (UWV is essentiële entiteit onder NIS2).

---

## 2. Context en kaders

### 2.1 UWV in de keten

| Onderdeel | Rol |
|---|---|
| **UWV** | Uitvoeringsorganisatie SZW: werknemersverzekeringen, sociaal-medische beoordeling, re-integratie, arbeidsmarkt- en gegevensdienstverlening |
| **SVB** | Volksverzekeringen, AOW, kinderbijslag |
| **Gemeenten** | Participatiewet, Wmo, Jeugdwet |
| **BKWI** (UWV-onderdeel) | Centrale broker SUWI-stelsel, beheert **Suwinet** / GeVS |
| **Inlichtingenbureau (IB)** | Decentrale broker, primair voor gemeenten |
| **Belastingdienst** | Aangifte loonheffingen → bron polisadministratie |
| **CBS** | Statistische verwerking |

### 2.2 UWV-interne kaders

- **WDAS** — Waardegedreven Data & Analytics Strategie (UWV-brede routekaart).
- **CGM** — Canoniek Gegevensmodel (UWV-conceptueel datamodel).
- **FUGEM** — Functioneel Gegevensmodel per domein, gekoppeld aan CGM via verticale data lineage.
- **MRM-beleid** — ModelRisicoManagement voor voorspellende algoritmes.
- **Algoritmeregister UWV** — publieke transparantie over ingezette algoritmes.
- **Dmap** — bestaand data- en advanced analytics platform; doel-doorontwikkeling.
- **AI Kernteam** — gap-analyse en governance op AI Act.
- **Open op Orde** — informatiehuishouding, Wet open overheid.

### 2.3 Externe kaders

| Kader | Reikwijdte voor UWV |
|---|---|
| **NORA** | Architectuurprincipes Nederlandse overheid |
| **KARWEI 2.5** | Ketenarchitectuur Werk & Inkomen (SUWI-domein) |
| **AVG** | Verwerking persoonsgegevens, incl. art. 9 (gezondheid) |
| **BIO / BIO2** | Informatiebeveiliging, gebaseerd op ISO 27001/27002:2022 |
| **NIS2** | UWV is **essentiële entiteit** (publieke administratie) |
| **AI Act** | Hoog-risico AI in publieke dienstverlening |
| **Wet SUWI / Besluit SUWI / Regeling SUWI** | Stelselwet en uitvoeringsregels |
| **Wfsv** | Doelgroepregister banenafspraak (art. 38d) |
| **Archiefwet 1995 / Woo** | Bewaring en openbaarheid |

---

## 3. Wettelijk kader en datadomeinen

Per wet gelden specifieke verwerkingsgrondslagen, doelen, bewaartermijnen en gegevenstypen. Deze worden in het platform vertaald naar **dataclassificaties**, **toegangsrollen** en **doelbindings-policies** (policy-as-code).

### 3.1 WW (Werkloosheidswet)
- **Doel**: vaststellen en uitkeren WW.
- **Bronnen**: aangifte loonheffingen (Belastingdienst → polisadministratie), werkmap, sollicitatieactiviteiten, opzeggingsbrieven, beschikkingen.
- **Bijzonderheden**: dagloonberekening; "verwijtbaar werkloos"-toets (waarvoor UWV nu een risicomodel gebruikt).

### 3.2 WIA (Wet werk en inkomen naar arbeidsvermogen)
- **Onderdelen**: WGA (gedeeltelijk arbeidsongeschikt), IVA (volledig en duurzaam).
- **Bronnen**: re-integratieverslag werkgever, medische dossiers (verzekeringsarts), arbeidsdeskundige rapporten, claimbeoordeling, Actueel oordeel bedrijfsarts.
- **Bijzonderheden**: bevat **bijzondere persoonsgegevens** (gezondheid, art. 9 AVG); strikt gescheiden medische en niet-medische gegevensstromen; per september 2025 vereenvoudigde WIA-beoordeling 60+.

### 3.3 Wajong (Wet arbeidsongeschiktheidsvoorziening jonggehandicapten)
- **Regimes**: oude Wajong (vóór 2010), Wajong 2010, Wajong 2015 (alleen "duurzaam geen arbeidsvermogen"-route).
- **Bronnen**: medisch dossier, schoolinformatie (PrO/VSO), arbeidsmogelijkheden-onderzoek, participatieplan, loondispensatie-beschikkingen.
- **Bijzonderheden**: doelgroep is jong; extra zorgvuldigheid in profilering; tijdelijke regeling re-integratie IVA/Wajong-DGA loopt tot 21-04-2028.

### 3.4 Re-integratie & sociaal-medisch
- **Bronnen**: re-integratiedossier, plan van aanpak, eindevaluatie, deskundigenoordeel, contracten met re-integratiebedrijven, IPS-trajecten, proefplaatsingen, scholingsbudget.
- **Bijzonderheden**: ketenproces met externe partners (re-integratiebedrijven, GGZ); medische én sociaal-economische data verweven.

### 3.5 CRM-data UWV
- **Bronnen**: klantcontacten (telefoon, balie, beeldbellen), Werkmap-correspondentie, klacht- en bezwaarprocedures, klanttevredenheidsonderzoeken, kanaalvoorkeuren.
- **Bijzonderheden**: 360°-beeld vereist samenvoeging van uitkeringsadministratie, contactdata en re-integratiestatus → strenge doelbinding.

### 3.6 Financieel-Economische Zaken (FEZ)
- **Bronnen**: uitkeringslasten per wet, uitvoeringskosten, premies (Aof, Awf, Whk, Ufo), schadelast-prognoses, begroting/realisatie, treasury, leveranciers- en contractdata.
- **Bijzonderheden**: data overwegend geaggregeerd; koppeling met cliëntdata alleen voor actuariële doeleinden, gepseudonimiseerd.

### 3.7 Overige relevante domeinen
- **Polisadministratie** — feitelijk data-fundament (lonen, dienstverbanden, IKV's).
- **Doelgroepregister banenafspraak** (art. 38d Wfsv).
- **Handhaving & opsporing** (samen met SIOD en Nederlandse Arbeidsinspectie).
- **Arbeidsmarktinformatie** (sectorpublicaties UWV, vacaturedata).
- **HRM & bedrijfsvoering** (interne data, niet onder dit platform tenzij voor sturingsinformatie).

---

## 4. Architectuurprincipes

> Aanvullend op NORA-basisprincipes; nummering UWV-eigen. Elk principe is meetbaar en afdwingbaar via policy-as-code waar mogelijk.

| # | Principe | Implicatie |
|---|---|---|
| **P-01** | **Doelbinding by design** | Elke dataset/data product is gekoppeld aan ≥ 1 wettelijk doel; toegang/queries zonder geldig doel worden geblokkeerd of gelogd. |
| **P-02** | **Eenmalig vastleggen, meervoudig (her)gebruiken** | Polisadministratie en BRP-spiegels zijn single source; geen schaduwkopieën in domeinen. |
| **P-03** | **CGM is leidend** | Alle gold data products mappen 1-op-1 naar CGM-entiteiten; FUGEMs worden gekoppeld via verticale lineage. |
| **P-04** | **Federatief eigenaarschap** | Data products hebben een business-eigenaar in de divisie; Data Office faciliteert kaders. |
| **P-05** | **Zero-trust, least privilege, just-in-time** | Geen permanente brede toegang; rollen op basis van wettelijke taak. |
| **P-06** | **Pseudonimiseren tenzij** | Standaard pseudonimiseren; herleiden alleen via gecontroleerde re-identificatieservice met audit. |
| **P-07** | **Verklaarbaarheid van besluiten** | Elke geautomatiseerde of ondersteunde beslissing is reproduceerbaar en uitlegbaar (modellen + featurewaarden + versies). |
| **P-08** | **Open standaarden, open formats** | Iceberg/Delta, Parquet, OpenLineage, OpenAPI, SuwiML voor keten. |
| **P-09** | **Cloud waar het kan, on-prem/sovereign waar het moet** | Bijzondere persoonsgegevens en SUWI-keten alleen in EU-soevereine omgevingen. |
| **P-10** | **Auditeerbaar van A tot Z** | Onveranderbare logging van toegang, transformaties en modeluitkomsten; minimaal 6 maanden, langer voor besluitvormingsdata. |
| **P-11** | **Mens-in-de-lus voor impactvolle besluiten** | Geen volledig geautomatiseerde besluiten over uitkeringen die nadeel toebrengen (art. 22 AVG). |
| **P-12** | **Ethiek vooraf, niet achteraf** | DPIA, IAMA en bias-toetsing zijn poortwachters voor productiegang. |

---

## 5. Conceptuele referentiearchitectuur

### 5.1 Lagenmodel (high-level)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CONSUMPTIE                                                              │
│  Werkmap • UWV-medewerker dashboards • Power BI/SAS • Self-service       │
│  Gegevensdiensten naar ketenpartners (Suwinet) • Open data CBS/Woo       │
└─────────────────────────────────▲────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴────────────────────────────────────────┐
│  SEMANTISCHE LAAG  (CGM-aligned)                                         │
│  Data products (gold) • Feature store • Semantic models • API gateway    │
└─────────────────────────────────▲────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴────────────────────────────────────────┐
│  PROCESSING & ML                                                         │
│  Batch (Spark) • Streaming (Flink/Kafka) • dbt • MLflow • Notebooks      │
└─────────────────────────────────▲────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴────────────────────────────────────────┐
│  OPSLAG  (Lakehouse, medallion)                                          │
│  Bronze (raw, immutable) → Silver (geconformeerd, geanonimiseerd waar    │
│  mogelijk) → Gold (CGM-conform, business-ready) — Iceberg/Delta + S3/ADLS│
└─────────────────────────────────▲────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴────────────────────────────────────────┐
│  INGESTIE & INTEGRATIE                                                   │
│  Batch ETL • CDC • Event streaming (Kafka) • SuwiML adapters • API mgmt  │
└─────────────────────────────────▲────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴────────────────────────────────────────┐
│  BRONNEN                                                                 │
│  Polisadministratie • WIA/Wajong/WW-applicaties • CRM • FEZ-systemen     │
│  Re-integratie • Werkmap • Externe ketenpartners (BRP, Belastingdienst)  │
└──────────────────────────────────────────────────────────────────────────┘

CROSS-CUTTING (verticaal door alle lagen):
IAM & SSO • Data Catalog & Lineage • Security & Encryption • Observability
AI Governance & Algoritmeregister • Compliance & Audit • DataOps/MLOps
```

### 5.2 Zone-scheiding

| Zone | Inhoud | Toegang |
|---|---|---|
| **Raw / Bronze** | Onveranderbare brondata (incl. PII) | Alleen ingestion-services en data-engineers met JIT-toegang |
| **Conformed / Silver** | Schoongemaakt, gestandaardiseerd, gepseudonimiseerd waar mogelijk | Data-engineers en geprivilegieerde analisten |
| **Curated / Gold** | CGM-conforme data products per domein | Domein-gebruikers volgens RBAC/ABAC |
| **Sandbox** | Tijdelijke verkenning, alleen synthetische of geanonimiseerde data | Data scientists |
| **Sensitive Vault** | Bijzondere persoonsgegevens (medisch, strafrecht), sterk versleuteld | Strikt beperkte rollen, 4-eyes principe |

### 5.3 Domeinen (data mesh)

```
                    ┌────────────────────────────┐
                    │  Data Office UWV (centraal) │
                    │  CGM • Beleid • Toezicht    │
                    └─────────────┬──────────────┘
                                  │ kaders, policies, certificering
        ┌─────────────────────────┼────────────────────────────────┐
        ▼                         ▼                                ▼
┌──────────────┐      ┌──────────────────┐             ┌───────────────────┐
│ Domein WW    │      │ Domein AG        │             │ Domein FEZ        │
│ Data products│      │ (WIA/Wajong/ZW)  │             │ Data products     │
│ • dagloon    │      │ • claimbeoordeel │             │ • uitkeringslast  │
│ • verwijtb.  │      │ • re-integratie  │             │ • premieinning    │
│ • sollic.    │      │ • soc.med.cap    │             │ • schadelast      │
└──────────────┘      └──────────────────┘             └───────────────────┘
        ▲                         ▲                                ▲
┌──────────────┐      ┌──────────────────┐             ┌───────────────────┐
│ Domein CRM   │      │ Domein Handhav.  │             │ Domein Arbeidsmkt │
│ • klant 360  │      │ • risicomodellen │             │ • vacatures       │
│ • kanaal     │      │ • signaalverrijk │             │ • sectorprognose  │
└──────────────┘      └──────────────────┘             └───────────────────┘

Iedere domein-zone publiceert "data products" met:
  schema (in CGM-termen) • SLA • datakwaliteit • doel(en) • eigenaar •
  AVG-rechtsgrond • bewaartermijn • lineage • API/contract
```

---

## 6. Logische bouwblokken per laag

### 6.1 Bronlaag (selectie)

| Bron | Inhoud | Type |
|---|---|---|
| **Polisadministratie** | Lonen, dienstverbanden, IKV's | Master |
| **WIA-claimsysteem** | Aanvragen, beoordelingen, beschikkingen | Transactioneel |
| **Wajong-systeem** | Doelgroepbepaling, participatieplan | Transactioneel |
| **WW-uitkeringssysteem** | Aanvragen, betalingen, sollicitatiegegevens | Transactioneel |
| **Sociaal-medisch dossier (SMZ)** | Medische rapportages, verzekeringsarts, arbeidsdeskundige | Bijzonder PG |
| **Re-integratie-applicatie** | Trajecten, contracten met re-bedrijven, IPS, proefplaatsing | Transactioneel |
| **CRM (klantcontact + Werkmap)** | Berichten, telefoonlogs, kanaalkeuze, klachten | Transactioneel |
| **FEZ / ERP** | Grootboek, AP/AR, uitkeringen-betaalruns | Financieel |
| **Doelgroepregister banenafspraak** | Indicaties art. 38d Wfsv | Master |
| **BRP-spiegel** | Persoonsgegevens (via Logius) | Referentie |
| **Belastingdienst** | Aangifte loonheffingen | Extern |
| **Suwinet/GeVS via BKWI** | Ketengegevens | Extern |
| **CBS-leveringen** | Microdata, retour-statistiek | Extern |

### 6.2 Ingestie en integratie

- **Batch ETL/ELT**: Apache Airflow + dbt (silver→gold transformaties).
- **CDC**: Debezium / GoldenGate vanaf transactionele systemen.
- **Streaming**: Apache Kafka (event backbone), schema registry, dead-letter queues.
- **Keten-adapters**: SuwiML/XML adapters voor BKWI-koppelvlakken; SOAP/REST gateways.
- **API-management**: centrale gateway met OAuth2/OIDC, rate limiting, audit.
- **PII-detectie at ingest**: classificeert kolommen automatisch (BSN, IBAN, gezondheid) en stuurt naar passende zone.

### 6.3 Opslag (lakehouse)

- **Object storage**: S3-compatibel of ADLS Gen2 (afhankelijk van cloudkeuze).
- **Tabelformaat**: **Apache Iceberg** of **Delta Lake** (ACID, time travel, schema evolution, partition evolution).
- **Catalog**: Unity Catalog of Polaris/REST-catalog, integratie met Atlas/Purview voor governance.
- **Medallion**: bronze (raw immutable), silver (cleaned/conformed), gold (CGM-conform business products).
- **Sensitive Vault**: aparte kluis met envelope encryption + customer-managed keys (HSM-backed).

### 6.4 Processing en compute

- **Batch**: Apache Spark (Databricks of EMR/Synapse), dbt voor SQL-transformaties.
- **Streaming**: Apache Flink of Spark Structured Streaming.
- **Orchestratie**: Apache Airflow of Dagster.
- **Notebooks**: Jupyter/Databricks Notebooks, met enforcement van branches via Git.
- **Model training**: MLflow + Ray of distributed PyTorch; GPU-pools waar nodig (op-prem of sovereign cloud).

### 6.5 Semantische laag

- **Data products** als kerncontract richting consumenten (BI, ML, externe partners).
- **Feature store** (Feast of Tecton) met online/offline parity voor real-time scoring.
- **Semantische modellen** (dbt semantic layer of LookML-equivalent) voor consistente KPI's.
- **API-laag** voor data-as-a-product naar Werkmap, gegevensdiensten, en intern.

### 6.6 Consumptie

- **BI**: Power BI als primair tool (in lijn met huidige platform stack), met certified datasets.
- **Self-service analytics**: gecontroleerde sandboxes met geaggregeerde of gesynthetiseerde data.
- **Embedded analytics**: in Werkmap, behandelaarschermen, beoordelaarstools.
- **Gegevensdiensten naar derden**: via Suwinet/BKWI én via een nieuw API-platform (Mijn Gegevensdiensten 2.0).
- **Open data**: gepubliceerd via UWV.nl, CBS-leveringen, Woo-portaal.

---

## 7. Cross-cutting capabilities

### 7.1 Identity & Access Management

- **Centraal IdP**: Entra ID of Keycloak met SAML/OIDC.
- **MFA verplicht** voor alle gebruikers; **FIDO2/passkeys** voor privileged accounts.
- **Federatie**: eHerkenning voor werkgeversportalen; DigiD voor cliënten (via Werkmap).
- **RBAC + ABAC**: rollen op basis van wettelijke taak (bv. "Claims Analyst", "Fraud Analyst"), attributen op basis van regio, divisie, geclassificeerd niveau.
- **Privileged Access Management (PAM)**: jump hosts, session recording, just-in-time elevation.
- **Secret management**: HashiCorp Vault of Azure Key Vault, automatische rotatie.

### 7.2 Data governance

- **Data Catalog**: Microsoft Purview, Collibra of Atlas; verplichte velden bij elk data product:
  - eigenaar, steward, custodian
  - doel(en) en wettelijke grondslag
  - dataclassificatie (BIO + UWV-classificatie)
  - bewaartermijn en archiveringsbeleid
  - SLA en kwaliteitsmetrics
  - lineage (technisch en business, gekoppeld aan CGM)
- **CGM-koppeling**: elk gold-veld is gekoppeld aan een CGM-attribuut; afwijking vereist explicit waiver van Data Office.
- **FUGEM-integratie**: verticale lineage tussen FUGEM (domein) en CGM (UWV-breed).
- **Data contracts** tussen producent en consument met schema, SLA, kwaliteitsdrempels.
- **Data quality**: Great Expectations of Soda; metrics in dashboard per domein.
- **Master data management** voor klant (BSN, BRP-spiegel), werkgever (LH-nummer, KvK), wet/uitkeringssoort, regio.
- **Datalifecycle**: geautomatiseerde retentie en vernietiging (sluit aan op UWV-doel "vernietigen Q1 2025 voor 2 processen").

### 7.3 Security (BIO2 / NIS2)

- **Encryption at rest** (AES-256, customer-managed keys voor bijzondere gegevens).
- **Encryption in transit** (TLS 1.3).
- **Netwerksegmentatie**: VPC's per zone, private endpoints, geen publieke endpoints voor opslag.
- **Hardening**: CIS Benchmarks, Infrastructure as Code (Terraform), policy-as-code (OPA/Sentinel).
- **Vulnerability management**: continue scans (Trivy, Snyk), SLA's per criticality (kritiek ≤ 7 dagen).
- **SIEM/SOC**: integratie met Platform SOC; use-cases voor data-exfiltratie, anomalous queries op polisadministratie, privileged misuse.
- **Incident response**: 24-uurs early warning + 72-uurs incident report aan NCSC/CSIRT (NIS2).
- **Backup**: 3-2-1, immutable copies tegen ransomware, jaarlijks geteste DR.
- **Supply chain security**: SBOM voor kritieke componenten, leveranciers-TPM's (zoals UWV nu al doet voor datacenter en netwerk).

### 7.4 Observability

- **Metrics, logs, traces** via OpenTelemetry; dashboards per data product.
- **Audit logs**: onveranderbaar (WORM-storage), centraal SIEM, 7 jaar voor besluitvormingsdata.
- **Lineage telemetry**: OpenLineage voor automatische lineage-capture in pipelines.
- **Datakwaliteits-SLO's** per data product, alerts bij drift.

### 7.5 AI Governance & MLOps

- **Algoritmeregister UWV**: elk productie-algoritme is geregistreerd, openbaar voor zover geen handhavingsrisico.
- **MRM-beleid**: model registry verplicht; modellen doorlopen risicoclassificatie (laag/midden/hoog/onaanvaardbaar) conform AI Act.
- **Hoog-risico modellen** (bv. risicomodellen handhaving, ondersteunende modellen claimbeoordeling) volgen verzwaard regime: DPIA + IAMA, mens-in-de-lus, monitoring op drift en bias, jaarlijkse audit.
- **Model cards**: per model gepubliceerd (training data, doel, performance, fairness metrics, beperkingen).
- **Feature store** met versionering; geen ad-hoc features in productie.
- **Reproduceerbaarheid**: training, data en code versioned; herleidbaar tot besluit.
- **Verboden praktijken**: social scoring, predictieve fraudeprofielen op basis van wijk/etniciteit (lessen Toeslagenaffaire).

---

## 8. Fictieve use cases (uitgewerkt)

> 10 use cases die tezamen het platform stress-testen.

---

### UC-01 — Versnelling WIA-claimbeoordeling (sturingsinformatie)

**Probleem.** WIA-aanvragen stegen sinds 2022 met 31%, afhandelingen met 19,4%; eind 2025 wachten ruim 12.000 mensen langer dan de wettelijke termijn. Capaciteitssturing van verzekeringsartsen en arbeidsdeskundigen is suboptimaal.

**Doel.** Realtime inzicht in voorraad, doorlooptijden, wachtgelden (voorschotten), en voorspelling van workload per regio en specialisme.

**Data**:
- Bron: WIA-claimsysteem, capaciteitsplanning SMZ, voorschotbetalingen (FEZ), re-integratieverslagen.
- CGM-entiteiten: `Aanvraag`, `Beoordeling`, `Beoordelaar`, `Cliënt` (gepseudonimiseerd in stuurinfo).

**Architectuur**:
- CDC vanaf claimsysteem → bronze → silver (geanonimiseerd voor sturing) → gold data product `wia_claim_funnel`.
- Streaming events voor live KPI's (aantal aanvragen vandaag, gemiddelde wachttijd).
- Voorspelmodel (gradient boosting) voor verwachte instroom per kwartaal, op basis van macro-economische features (CBS) en historische seizoenspatronen.

**Compliance**:
- AVG: stuurinformatie geaggregeerd; geen herleidbaarheid tot individu in dashboards.
- BIO: toegang via rol "WIA-stuurinfo" (managers en planners).
- AI Act: laag risico (sturingsinfo, geen impact op individuen).

**Output**: dashboard "WIA Funnel" + capaciteitsmodel voor RvB.

---

### UC-02 — Voorspelmodel re-integratiekansen Wajongers

**Probleem.** Onderzoek "Wat werkt bij Wajongers" toonde dat naast harde dossierkenmerken ook zachte factoren (motivatie, omgeving) voorspellend zijn. UWV-arbeidsdeskundigen hebben behoefte aan beslissingsondersteuning bij keuze van re-integratietraject.

**Doel.** Decision support: per cliënt schatting van kans op duurzaam werk (≥ 6 mnd) bij verschillende interventies (IPS, proefplaatsing, scholing).

**Data**:
- Bron: Wajong-dossier, claimbeoordeling, participatieplan, eerder traject-uitkomsten, scholingsbudget-data, polisadministratie (werk-historie).
- Bijzondere PG: gezondheidsgegevens uit medisch dossier — alleen via Sensitive Vault.

**Architectuur**:
- Feature store met cliënt-features (gepseudonimiseerd; re-identificatie alleen door arbeidsdeskundige in eigen dossier).
- ML-pipeline (XGBoost + uitlegbaarheid via SHAP) in MLflow.
- Verklaarbaarheidslaag: top-3 drivers per voorspelling getoond aan arbeidsdeskundige.
- **Mens-in-de-lus**: model adviseert, beslissing blijft bij arbeidsdeskundige. Logging van wel/niet opvolgen.

**Compliance**:
- **AI Act: hoog risico** (toegang tot essentiële openbare diensten, art. 6/Annex III). Verzwaard regime: DPIA, IAMA, risicomanagement, monitoring, model card, registratie EU-database.
- **AVG art. 22**: geen volledig geautomatiseerd besluit.
- **AVG art. 9**: gezondheidsgegevens, grondslag art. 9 lid 2 onder h (sociale zekerheid).
- Bias-toetsing op leeftijd, geslacht, herkomst, regio; ondergrens fairness metrics.
- Jaarlijkse externe audit, uitkomsten in algoritmeregister.

**Output**: beslissingsondersteuning in dossiersysteem arbeidsdeskundige.

---

### UC-03 — Verbeterd "verwijtbaar werkloos"-risicomodel (WW)

**Context.** UWV gebruikt een risicomodel voor WW-aanvragen. De Algemene Rekenkamer (mei 2025) oordeelde dat het model 3× effectiever is dan willekeurige controle en "grotendeels op orde", maar IT-beheer van de risicoscan vraagt aandacht.

**Doel.** Nieuwe versie van het model op moderne MLOps-stack, met sterkere monitoring en uitlegbaarheid.

**Data**:
- Bron: WW-aanvraag, opzeggingsdocumenten (gestructureerd via NLP-extractie), arbeidsverleden polisadministratie, eerdere uitkomsten verwijtbaarheidstoets.

**Architectuur**:
- Data ingestie streaming (zodra aanvraag binnen) → feature store → model serving → behandelschermen.
- A/B-testing capability om modelversies te vergelijken.
- Drift detection (data drift en concept drift) met alerts.
- Champion-challenger setup.

**Compliance**:
- **AI Act**: vermoedelijk hoog risico (toegang tot uitkering). Volledig regime.
- Mens-in-de-lus: model selecteert dossiers voor handmatige controle; behandelaar beslist.
- Volledig auditspoor van model → score → behandeling → besluit.
- Geregistreerd in algoritmeregister UWV (zoals nu al gebeurt).

**Output**: triagering van WW-dossiers naar behandelaar.

---

### UC-04 — Proactieve TW-aanvulling (Wet proactieve dienstverlening SZW)

**Context.** Het wetsvoorstel proactieve dienstverlening SZW (2025) creëert grondslag om burgers actief te wijzen op rechten waar ze geen aanvraag voor hebben gedaan. Voor TW-aanvulling gebeurt dit deels al gecombineerd met WW-aanvragen.

**Doel.** Detecteren van cliënten die mogelijk recht hebben op TW maar geen aanvulling ontvangen, en hen proactief benaderen.

**Data**:
- WW/WIA/Wajong-uitkering, hoogte, partnerinkomen (waar bekend), polisadministratie, BRP (huishoudsamenstelling).
- Uitsluitend de gegevens noodzakelijk voor TW-toets (doelbinding strikt afgebakend).

**Architectuur**:
- Periodieke batch-job die uitkeringspopulatie scant op TW-eligibility.
- Output: lijst potentieel rechthebbenden voor cliëntcommunicatie via Werkmap.
- Geen scoring of profilering — regel-gebaseerde toets met expliciete drempelwaarden.

**Compliance**:
- AVG art. 6 lid 1 onder e (publieke taak), grondslag in voorgenomen Wet proactieve dienstverlening SZW.
- DPIA verplicht; doelbinding zorgvuldig afgebakend.
- Geen profilering die individu negatief raakt — uitsluitend faciliterend.
- Logging welke cliënten zijn benaderd, met opt-out mogelijkheid.

**Output**: proactieve berichten in Werkmap met "u heeft mogelijk recht op TW-aanvulling".

---

### UC-05 — 360°-cliëntbeeld voor klantcontact (CRM)

**Probleem.** Klanten met meerdere uitkeringen (bv. WW + TW, of WIA + Wajong) moeten nu door medewerkers via meerdere systemen worden bediend. Werkmap, telefoon en balie hebben geen samenhangend beeld.

**Doel.** Eén geïntegreerd cliëntbeeld voor UWV-medewerkers, gebouwd op het dataplatform en ontsloten naar CRM-applicatie.

**Data**:
- Uitkeringsadministraties WW/WIA/Wajong/ZW, klantcontactlogs, Werkmap-berichten, kanaalvoorkeuren, klachten/bezwaren, betalingsstatus, lopende re-integratietrajecten.

**Architectuur**:
- Gold data product `client_360` met CGM-conform schema.
- Real-time API (lage latency, OAuth2) vanuit feature store voor CRM en Werkmap.
- Caching layer voor performance.
- **Glass box logging**: elke API-call gelogd met aanleiding ("ticket #X") en doel.

**Compliance**:
- **Doelbinding**: medewerker mag alleen velden zien die nodig zijn voor zijn rol/taak (column-level security via ABAC).
- AVG art. 5: geen "alles is altijd zichtbaar"; expliciete rol-gebaseerde projecties.
- Audittrail per inzage (lessons learned uit Suwinet-AP-onderzoek 2014).
- Quarterly access review op rol- en attribuut-toekenningen.

**Output**: API en UI-component voor CRM/Werkmap.

---

### UC-06 — Schadelast- en uitkeringslastprognose (FEZ)

**Probleem.** Begrotingscyclus en raming uitkeringslasten vereist actuele en goed onderbouwde prognoses. WIA-volume stijgt, afschaffing IVA staat ter discussie — beleidsscenario's moeten doorgerekend kunnen worden.

**Doel.** Actuariele modellen voor 5-jaars uitkeringslastprognose per wet, met scenario-analyse.

**Data**:
- Geaggregeerde uitkeringsdata per wet (WW, WIA, Wajong, ZW, WAO, TW), instroom/uitstroom-volumes, demografische trends (CBS), economische indicatoren (CPB), historische schadelast.
- **Geen herleidbare cliëntdata** — alleen geaggregeerd of gepseudonimiseerd.

**Architectuur**:
- Tijdreeksmodellen (Prophet, statsforecast) + macroscenario's.
- Scenario-engine waarmee beleidsmedewerkers parameters kunnen wijzigen ("wat als IVA wordt afgeschaft per 2027?").
- Reproduceerbare runs met versionering van inputs en aannames.

**Compliance**:
- AVG: verwerking grotendeels geanonimiseerd → buiten scope of minimale impact.
- Maar: model-aannames en inputs worden gedocumenteerd voor verantwoording aan Tweede Kamer.
- Open data uitkomsten gepubliceerd via UWV.nl en jaarverslag.

**Output**: dashboard "Uitkeringslast 2026–2030" + scenario-tool voor beleidsdirectie en SZW.

---

### UC-07 — Datakwaliteit polisadministratie

**Probleem.** Polisadministratie (21,2 mln IKV's, 13,8 mln personen) is fundament voor dagloon, WW, WIA, en gegevensleveringen. Fouten in IKV's leiden tot fouten in uitkeringen.

**Doel.** Continue datakwaliteits-monitoring met automatische detectie van afwijkingen en correctievoorstellen.

**Data**:
- Aangifte loonheffingen (Belastingdienst), polisadministratie, BRP-spiegel, eerdere correcties.
- Cross-reference met andere bronnen (bv. detectie inconsistenties tussen aangiftes en pensioenfondsdata).

**Architectuur**:
- Streaming validatie (Great Expectations) bij inkomende aangiftes.
- Anomalie-detectie (isolation forest) op verdachte loonpatronen.
- Dashboard voor datasteward Polisadministratie.
- Feedback loop naar werkgevers via reguliere kanalen.

**Compliance**:
- AVG juistheidsprincipe (art. 5 lid 1 onder d) — actief invulling.
- Doelbinding: kwaliteitscontrole is afgeleid doel; toegestaan binnen Wet SUWI.
- Maatregelen "verkeerd loon" worden gelogd met grondslag.

**Output**: kwaliteitsdashboard + workflow voor correcties.

---

### UC-08 — Capaciteitsplanning sociaal-medische beoordelingen

**Probleem.** Tekort aan verzekeringsartsen → wachtlijsten WIA en Wajong. Planning gebeurt deels handmatig.

**Doel.** Geoptimaliseerde toewijzing van beoordelingen aan beoordelaars op basis van expertise, locatie, complexiteit en wachttijd.

**Data**:
- Roosters verzekeringsartsen/arbeidsdeskundigen, dossier-complexiteit (gederiveerd), locatievoorkeuren cliënt, doorlooptijd-targets, wettelijke termijnen.

**Architectuur**:
- Optimalisatie-engine (constrained optimization, OR-Tools) draait nightly.
- Voorgestelde planning naar planners; menselijk akkoord verplicht.
- Feedback loop: planners markeren slechte voorstellen → model leert.

**Compliance**:
- AVG: medewerkergegevens (planning) — grondslag arbeidsovereenkomst en gerechtvaardigd belang.
- Cliëntdata gepseudonimiseerd in planning.
- Geen geautomatiseerd besluit met impact op individu (gaat over interne planning).

**Output**: planning-tool voor SMZ-coördinatoren.

---

### UC-09 — Effectmeting re-integratie-instrumenten

**Probleem.** UWV zet jaarlijks honderden miljoenen in op re-integratie (sollicitatietraining, scholing, IPS, proefplaatsingen, jobcoaching). Welke instrumenten werken voor welke doelgroep?

**Doel.** Causale-inferentie analyses (quasi-experimentele methoden, propensity score matching) op effectiviteit per instrument × doelgroep.

**Data**:
- Re-integratiedossier, polisadministratie (post-traject werk), Wajong/WIA-status, demografie, kosten per traject.

**Architectuur**:
- Onderzoeksomgeving (sandbox) met gepseudonimiseerde panels.
- Rekenomgeving voor data scientists, met gestandaardiseerde pipelines (causalml, doWhy).
- Resultaten gepubliceerd in `odap.io/kennis` (vergelijkbaar met "Wat werkt bij Wajongers" 2011).

**Compliance**:
- AVG: verenigbaar gebruik (art. 5 lid 1 onder b) voor wetenschappelijk/statistisch doel.
- Sterke pseudonimisering, geen herleiding nodig.
- DPIA voor onderzoekspijplijn.
- Resultaten transparant publiek.

**Output**: kennisrapporten + interne beleidsondersteuning.

---

### UC-10 — Modernisering gegevensdiensten naar ketenpartners

**Context.** Suwinet-Inkijk en weekleveringen zijn verouderd. Ketenpartners (gemeenten, IND, DUO, Belastingdienst, deurwaarders) verwachten moderne API's met fijnmazige doelbinding.

**Doel.** "Mijn Gegevensdiensten 2.0": API-gateway voor real-time bevraging op CGM-gold data products, met expliciete doelbinding per call.

**Data**:
- Polisadministratie, dagloon, IKV-status, lopende uitkeringen — alle CGM-conform.

**Architectuur**:
- API gateway met OAuth2 client credentials per afnemende partij.
- **Doelcode in elke API-call** (bv. "WMO-toets gemeente X"); call wordt afgewezen als doel niet matcht met afnemerscontract.
- Filter op selectiecriteria (regio, leeftijd) zoals huidige Suwinet-praktijk.
- Volledige auditlog naar SOC + naar afnemende partij (transparantie).
- Backwards compatibility met SuwiML voor partijen die nog niet over zijn.

**Compliance**:
- Wet SUWI / Besluit SUWI doelbinding strikt afdwingen.
- AVG: rechtsgrond per afnemer expliciet vastgelegd.
- BIO/NIS2: encryption, MFA voor beheer, monitoring.
- Lessons learned uit AP-onderzoek Suwinet (2014): verwerkersovereenkomsten compleet, periodieke controle op afnemers-naleving.

**Output**: nieuwe API-platform + transitie-roadmap voor afnemers.

---

## 9. Technologiekeuzes (illustratief)

> Niet-prescriptief; bedoeld als realistische landing zone. Definitieve keuzes via aanbesteding en pilots.

| Laag | Optie A (Microsoft-georiënteerd) | Optie B (Open source / multi-cloud) |
|---|---|---|
| Cloud | Azure (sovereign) | Hybride: AWS Sovereign + on-prem |
| Object storage | ADLS Gen2 | S3-compatible (MinIO on-prem + AWS) |
| Tabelformaat | Delta Lake | Apache Iceberg |
| Compute | Microsoft Fabric / Databricks | Databricks / EMR / Trino |
| Streaming | Event Hubs + Stream Analytics | Confluent Kafka + Flink |
| Orchestratie | Azure Data Factory + Airflow | Airflow / Dagster |
| Catalog | Microsoft Purview | DataHub / OpenMetadata |
| Lineage | Purview + native Fabric | OpenLineage + Marquez |
| MLOps | Azure ML + MLflow | MLflow + Kubeflow |
| BI | Power BI (huidige UWV-keuze) | Power BI + Apache Superset |
| Identity | Entra ID | Keycloak |
| Secrets | Azure Key Vault | HashiCorp Vault |
| SIEM | Sentinel | Splunk / Elastic |

**Aandachtspunten:**
- Bijzondere persoonsgegevens (medisch) **alleen** in EU/NL-soevereine regio's.
- BKWI/Suwinet-componenten blijven vooralsnog grotendeels on-premises i.v.m. ketenkoppeling en historie.
- Vendor-onafhankelijke datalagen (Iceberg) borgen exit-mogelijkheden.

---

## 10. Compliance-mapping (samenvatting)

| Kader | Belangrijkste maatregelen in dit platform |
|---|---|
| **NORA** | Open standaarden, hergebruik via CGM, federatieve identiteit, transparantie via algoritmeregister |
| **AVG** | Doelbinding policy-as-code, pseudonimisering by default, Sensitive Vault, DPIA per use case, mens-in-de-lus, audittrails per inzage, retentie automatiseren |
| **BIO2 / ISO 27001:2022** | ISMS, BIV-classificatie, encryption at rest + in transit, MFA, network segmentation, hardening (CIS), SOC, immutable backups |
| **NIS2** | Bestuurlijke verantwoordelijkheid, all-hazards risicomanagement, supply chain security (SBOM, TPM's), 24/72-uurs meldplicht, vulnerability disclosure-beleid, awareness-training, crisismanagement |
| **AI Act** | Risicoclassificatie per model, hoog-risico regime voor besluitvormingsondersteunende modellen, model cards, EU-registratie, monitoring, mens-in-de-lus, verboden praktijken expliciet uitgesloten |
| **Wet SUWI** | Strikte doelbinding op gegevensleveringen, BKWI-positie geborgd, KARWEI-conformiteit |
| **Archiefwet / Woo** | Lifecycle management, openbaarmaking via Woo-portaal voor niet-vertrouwelijke data, algoritmeregister publiek |

---

## 11. Migratie en roadmap (indicatief, 3 jaar)

### Jaar 1 — Fundament
- Doelarchitectuur en governance vastleggen; CGM-coverage uitbreiden (in lijn met huidige UWV-vacature voor CGM-uitbreiding).
- Lakehouse landing zone opleveren in soevereine cloud.
- DTAP-omgevingen volledig in gebruik (bouwt voort op huidige Dmap-stappen).
- Polisadministratie als eerste bron volledig gemodelleerd in CGM gold.
- Algoritmeregister en MRM volledig ingevoerd; AI Act gap-analyse afgerond (loopt al via AI Kernteam).
- Eerste 2 use cases live: UC-07 datakwaliteit polisadministratie + UC-01 WIA funnel.
- BIO2-baseline afgedwongen via policy-as-code.

### Jaar 2 — Schaal
- Domeinen WW, AG, FEZ, CRM gefedereerd ingericht.
- Use cases UC-03 (verbeterd WW-risicomodel), UC-05 (360°-cliënt), UC-06 (schadelastprognose), UC-08 (capaciteitsplanning).
- Modernisering gegevensdiensten — UC-10 in pilot.
- OpenVMS-uitfasering parallel; nieuwe systemen leveren direct CDC aan platform.
- NIS2-meldplicht-procedures volledig geoefend (tabletop én technisch).

### Jaar 3 — Innovatie & doorzetten
- UC-02 (Wajong re-integratiekansen) live na DPIA + IAMA + EU-registratie.
- UC-04 (proactieve TW) na inwerkingtreding Wet proactieve dienstverlening SZW.
- UC-09 (effectmeting re-integratie) als doorlopend onderzoeksprogramma.
- Legacy data warehouses (SQL Server stack) uitgefaseerd naar lakehouse.
- BI-rationalisatie: < 5 BI-tools UWV-breed (in lijn met WDAS-ambitie).

---

## 12. Risico's en aandachtspunten

| Risico | Mitigatie |
|---|---|
| **Lessons learned Toeslagenaffaire / Risicoscan Verblijf Buitenland**: profilering kan onbedoeld discrimineren | IAMA + DPIA verplicht, fairness-toetsing op beschermde kenmerken, expliciete uitsluiting van wijk/etniciteit als feature, externe audit jaarlijks, algoritmeregister publiek |
| **Bijzondere persoonsgegevens (gezondheid)** lekken via cross-domein joins | Sensitive Vault met aparte sleutels, geen joins zonder expliciete autorisatie, query-firewall |
| **Vendor lock-in cloudleverancier** | Iceberg/Delta + Parquet, exit-strategie in contracten, multi-cloud waar haalbaar, NL/EU-soevereiniteit |
| **Schaduw-IT / dark data** | Centrale catalog verplicht; data-zonder-eigenaar wordt gequarantaineerd |
| **Sociaal-medisch personeelstekort blokkeert use cases** | Capaciteitsplanning en effectmeting prioriteren (UC-08, UC-09); model-ondersteuning waar dat helpt zonder besluitvorming over te nemen |
| **Wachtlijst WIA leidt tot druk om te automatiseren** | Vasthouden aan mens-in-de-lus principe; modellen ondersteunen, beslissen niet |
| **Suwinet-historische bevindingen AP** (2014, 2018) | Continu monitoren afnemers-compliance; periodieke audits; expliciete doelcode per API-call |
| **NIS2-meldplicht missen** | Geoefend incidentproces met tijdsklokken; SOC-runbooks; crisis-comm via meerdere kanalen versleuteld |
| **AI Act non-compliance hoge boetes** | EU-registratie hoog-risico modellen tijdig (deadline aug 2026 voor hoog-risico); model cards openbaar; fundamental rights impact assessment |
| **Datakwaliteit blokkeert betrouwbare beslissingen** | UC-07 als prioriteit; data contracts met SLA's; quality gates in pipelines |

---

## Bijlage A — Mapping use cases naar wetten en CGM

| Use case | Wet(ten) | CGM-entiteiten (illustratief) | AVG-grondslag |
|---|---|---|---|
| UC-01 WIA Funnel | WIA | Aanvraag, Beoordeling, Beoordelaar | art. 6 lid 1e |
| UC-02 Wajong re-integratie | Wajong, Wet WIA | Cliënt, Diagnose, Traject, Werkhervatting | art. 6 lid 1e + 9 lid 2h |
| UC-03 WW verwijtbaar | WW | Aanvraag, Dienstverband, Ontslag | art. 6 lid 1e |
| UC-04 Proactieve TW | TW (+ moederwet) | Uitkering, Inkomen, Huishouden | art. 6 lid 1e (Wet proactieve DV) |
| UC-05 Cliënt 360 | Alle | Cliënt, Uitkering, Contact, Kanaal | art. 6 lid 1e |
| UC-06 Schadelast | WW, WIA, Wajong, ZW | Aggregaten | n.v.t. (geen PG) |
| UC-07 DQ Polisadm. | Wet SUWI, Wfsv | IKV, Werknemer, Werkgever | art. 6 lid 1c+e |
| UC-08 SMZ-planning | WIA, Wajong | Beoordelaar, Capaciteit | art. 6 lid 1b+f |
| UC-09 Re-integratie effectmeting | Wajong, WIA | Traject, Uitkomst | art. 5 lid 1b (verenigbaar gebruik) |
| UC-10 Mijn Gegevensdiensten 2.0 | Wet SUWI, Wfsv, BAG, BVV | Polisadm., Doelgroepregister | art. 6 lid 1c (per afnemer) |

---

## Bijlage B — Glossary

| Term | Betekenis |
|---|---|
| **AG** | Arbeidsongeschiktheid (umbrella voor WIA, WAO, Wajong, ZW) |
| **AKO** | Arbeidsmarkt, Klant en Ondersteuning (intern domein) |
| **BKWI** | Bureau Keteninformatisering Werk en Inkomen (UWV-onderdeel) |
| **CGM** | Canoniek Gegevensmodel (UWV) |
| **DGA** | Duurzaam Geen Arbeidsvermogen (Wajong-categorie) |
| **Dmap** | UWV's huidige data- en analytics-platform |
| **FEZ** | Financieel-Economische Zaken |
| **FUGEM** | Functioneel Gegevensmodel (domeinmodel) |
| **GeVS** | Gezamenlijke elektronische Voorzieningen SUWI (= Suwinet) |
| **IAMA** | Impact Assessment Mensenrechten en Algoritmes |
| **IB** | Inlichtingenbureau |
| **IKV** | Inkomstenverhouding (kerneenheid polisadministratie) |
| **IPS** | Individual Placement and Support (re-integratiemethode) |
| **IVA** | Inkomensvoorziening Volledig Arbeidsongeschikten |
| **KARWEI** | Ketenarchitectuur Werk en Inkomen |
| **MRM** | ModelRisicoManagement |
| **PG** | Persoonsgegeven |
| **SMZ** | Sociaal-Medische Zaken |
| **SuwiML** | XML-standaard voor SUWI-gegevensuitwisseling |
| **TW** | Toeslagenwet |
| **WDAS** | Waardegedreven Data & Analytics Strategie |
| **WGA** | Werkhervatting Gedeeltelijk Arbeidsongeschikten |
| **WTL** | Wet Tegemoetkomingen Loondomein |
| **Wfsv** | Wet financiering sociale verzekeringen |

---

*Dit is een fictieve, illustratieve referentiearchitectuur op basis van publiek beschikbare informatie over UWV's strategie en kaders. Voor implementatie zijn aanbestedingen, samenwerking met Data Office UWV / BKWI / SZW, en formele goedkeuring door FG, CISO, AI Kernteam en RvB nodig.*
