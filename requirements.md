# Requirements — Compliant Modern Data & Analyseplatform

**Kaders:** NORA · AVG · BIO/BIO2 · NIS2
**Scope:** ingestie, opslag (lakehouse/DWH), verwerking, governance, BI/analytics, ML/AI, IAM, observability.

---

## 1. Inleiding

Dit document beschrijft de eisen waaraan een modern data- en analyseplatform moet voldoen om compliant te zijn met de relevante Nederlandse en Europese kaders. De eisen zijn gegroepeerd per thema; per requirement is de herkomst aangegeven met `[NORA]`, `[AVG]`, `[BIO]`, `[NIS2]`.

> **Let op:** BIO wordt vervangen door BIO2, gebaseerd op ISO/IEC 27001:2022 en aangevuld met overheidsspecifieke maatregelen, mede om aansluiting te realiseren met NIS2. Waar BIO genoemd wordt, geldt BIO2 voor nieuwe implementaties.

---

## 2. Architectuur- en ontwerpprincipes (NORA)

### 2.1 Algemene principes
- **R-NORA-01** Het platform ondersteunt het **eenmalig vastleggen, meervoudig gebruiken** van data via een centrale catalogus en gestandaardiseerde data products. `[NORA]`
- **R-NORA-02** Data en functionaliteit worden ontsloten via **gestandaardiseerde, open API's** (REST/GraphQL/JDBC) met versionering. `[NORA]`
- **R-NORA-03** Het platform is **modulair en loosely coupled** opgebouwd, zodat componenten vervangbaar zijn zonder ketenbrede impact. `[NORA]`
- **R-NORA-04** **Open standaarden** (Apache Iceberg/Delta, Parquet, OpenAPI, OAuth2/OIDC, SAML) hebben voorrang boven proprietary formaten. `[NORA]`
- **R-NORA-05** **Vendor lock-in** wordt voorkomen door portable open-source formaten en exit-strategieën in contracten. `[NORA]`
- **R-NORA-06** Data is **vindbaar, toegankelijk, interoperabel en herbruikbaar** (FAIR-principes) via een data catalog met metadata, eigenaarschap en lineage. `[NORA]`
- **R-NORA-07** Diensten zijn **transparant, proactief en betrouwbaar** — keuzes en datastromen zijn herleidbaar voor betrokkenen en toezichthouders. `[NORA]`

### 2.2 Federatie en interoperabiliteit
- **R-NORA-08** Identiteits- en toegangsbeheer sluit aan op **federatieve voorzieningen** (DigiD, eHerkenning, eIDAS waar relevant) of vergelijkbare enterprise IdP's. `[NORA]`
- **R-NORA-09** Semantische interoperabiliteit via **gemeenschappelijke begrippenkaders** (bijv. Stelselcatalogus, sectorale woordenboeken) en machine-readable definities. `[NORA]`

---

## 3. Privacy & gegevensbescherming (AVG)

### 3.1 Rechtmatigheid en verantwoordingsplicht
- **R-AVG-01** Voor elke verwerking is een **rechtsgrond** vastgelegd (art. 6 AVG) en — bij bijzondere persoonsgegevens — een uitzonderingsgrond (art. 9). `[AVG]`
- **R-AVG-02** Het platform houdt een **verwerkingsregister** (art. 30) met doelen, categorieën, ontvangers, bewaartermijnen en beveiligingsmaatregelen. `[AVG]`
- **R-AVG-03** Voor verwerkingen met **hoog risico** is een **DPIA** uitgevoerd en periodiek geëvalueerd (art. 35). `[AVG]`
- **R-AVG-04** Verwerkersovereenkomsten (art. 28) zijn aanwezig voor alle (sub)verwerkers, inclusief cloudleveranciers. `[AVG]`

### 3.2 Privacy by design & by default
- **R-AVG-05** **Dataminimalisatie**: pipelines en modellen verwerken alleen velden die strikt nodig zijn; selectie wordt als configuratie afgedwongen. `[AVG]`
- **R-AVG-06** **Doelbinding**: per dataset/data product zijn toegestane doelen vastgelegd; hergebruik buiten doel vereist nieuwe grondslag-toets. `[AVG]`
- **R-AVG-07** **Pseudonimisering en anonimisering** zijn standaard beschikbaar (hashing, tokenisatie, k-anonimiteit, differential privacy waar passend). `[AVG]`
- **R-AVG-08** **Bewaartermijnen** zijn per dataset gedefinieerd; geautomatiseerde verwijdering/archivering is geïmplementeerd. `[AVG]`
- **R-AVG-09** Privacy-instellingen zijn **standaard restrictief** (minst privileges, beperkte zichtbaarheid). `[AVG]`

### 3.3 Rechten van betrokkenen
- **R-AVG-10** Het platform faciliteert **inzage, rectificatie, verwijdering, beperking, dataportabiliteit en bezwaar** (art. 15–22) via geautomatiseerde processen of duidelijke procedures. `[AVG]`
- **R-AVG-11** **Subject Access Requests** zijn herleidbaar over alle datalagen (lake → DWH → marts → ML features) via lineage-koppeling. `[AVG]`
- **R-AVG-12** Bij **geautomatiseerde besluitvorming/profilering** (art. 22) is menselijke tussenkomst en uitlegbaarheid van modellen voorzien. `[AVG]`

### 3.4 Doorgifte en lokatie
- **R-AVG-13** **Doorgifte buiten EER** alleen onder geldig mechanisme (adequaatheidsbesluit, SCC's, BCR's) inclusief **Transfer Impact Assessment**. `[AVG]`
- **R-AVG-14** Datalocatie en verwerkingslocatie zijn **transparant en configureerbaar** (regio-pinning, sovereign cloud waar vereist). `[AVG]`

### 3.5 Inbreukmeldingen
- **R-AVG-15** **Datalekdetectie en -registratie** binnen 72 uur richting AP, met procedure, rolverdeling en oefeningen. `[AVG] [NIS2]`

---

## 4. Informatiebeveiliging (BIO/BIO2)

### 4.1 Governance en risicomanagement
- **R-BIO-01** **Information Security Management System (ISMS)** conform ISO 27001 met scope, beleid, doelstellingen en directiebetrokkenheid. `[BIO]`
- **R-BIO-02** **Risicoanalyse** per dataset/dienst met BIV-classificatie (Beschikbaarheid, Integriteit, Vertrouwelijkheid) en behandelplan. `[BIO]`
- **R-BIO-03** **Verklaring van Toepasselijkheid (SoA)** met onderbouwing van geselecteerde maatregelen. `[BIO]`
- **R-BIO-04** Periodieke **interne audits** en management review; bevindingen via een tracker met SLA's afgehandeld. `[BIO]`

### 4.2 Identity & Access Management
- **R-BIO-05** **Centraal IAM** met SSO (OIDC/SAML), MFA verplicht voor alle gebruikers, sterkere MFA voor beheerders. `[BIO] [NIS2]`
- **R-BIO-06** **RBAC en/of ABAC** met least-privilege, just-in-time access en periodieke recertificering (≥ jaarlijks, kwartaal voor privileged). `[BIO]`
- **R-BIO-07** **Privileged Access Management (PAM)** met session recording, jump hosts en break-glass procedures. `[BIO]`
- **R-BIO-08** Service-accounts en machine-identiteiten via **secrets manager** met automatische rotatie. `[BIO]`

### 4.3 Cryptografie en datasecurity
- **R-BIO-09** **Encryption at rest** voor alle data (AES-256 of gelijkwaardig); **encryption in transit** met TLS 1.2+ (1.3 voorkeur). `[BIO]`
- **R-BIO-10** **Sleutelbeheer** via HSM/KMS, eigen sleutels (BYOK/HYOK) waar vereist; documentatie van sleutellevenscyclus. `[BIO]`
- **R-BIO-11** **Column-/row-level security** en **data masking** (statisch en dynamisch) op basis van rol en classificatie. `[BIO] [AVG]`
- **R-BIO-12** **Dataclassificatie** (publiek, intern, vertrouwelijk, geheim) is verplicht metadata; tooling dwingt classificatie af bij ingestie. `[BIO]`

### 4.4 Netwerk- en infrastructuurbeveiliging
- **R-BIO-13** **Netwerksegmentatie** (VPC, subnets, private endpoints) en **zero-trust**-principes; geen directe internet-exposure van dataopslag. `[BIO] [NIS2]`
- **R-BIO-14** **Hardening** conform CIS Benchmarks of vergelijkbaar; configuratie via Infrastructure as Code en policy-as-code (OPA, Sentinel). `[BIO]`
- **R-BIO-15** **Vulnerability management**: continue scans (containers, IaC, dependencies), SLA's voor patching naar criticality. `[BIO] [NIS2]`
- **R-BIO-16** **Endpoint protection** voor beheerwerkplekken; toegang tot productie alleen via gehardende workstations of bastion. `[BIO]`

### 4.5 Veilige ontwikkeling
- **R-BIO-17** **Secure SDLC** met threat modeling, code review, SAST/DAST/SCA, secret scanning in CI/CD. `[BIO]`
- **R-BIO-18** **Scheiding ontwikkel-/test-/productieomgevingen** met gescheiden credentials en synthetische of geanonimiseerde testdata. `[BIO] [AVG]`
- **R-BIO-19** **Change management** met goedkeuringen, rollback-plan en geautomatiseerde deploys (GitOps). `[BIO]`

### 4.6 Logging, monitoring en incident response
- **R-BIO-20** **Centrale logging** (toegang, queries, dataverandering, admin acties) onveranderbaar opgeslagen, minimaal 6 maanden, langer waar voorgeschreven. `[BIO] [AVG]`
- **R-BIO-21** **SIEM/SOC**-integratie met use-cases voor data-exfiltratie, anomalieën in toegang en privileged misuse. `[BIO] [NIS2]`
- **R-BIO-22** **Incident response plan** met rollen, runbooks, communicatie en jaarlijkse oefening (tabletop + technische). `[BIO] [NIS2]`

### 4.7 Bedrijfscontinuïteit
- **R-BIO-23** **Backup & recovery** met 3-2-1-strategie of gelijkwaardig, immutable/air-gapped backups tegen ransomware, getest herstel. `[BIO] [NIS2]`
- **R-BIO-24** **RTO/RPO** zijn per dienst vastgesteld; DR-tests minimaal jaarlijks en herleidbaar. `[BIO] [NIS2]`

---

## 5. Cyberweerbaarheid (NIS2 — voor essentiële/belangrijke entiteiten)

> NIS2 raakt veel publieke en private organisaties (waaronder digitale infrastructuur, overheid, gezondheid, drinkwater, transport, financiële sector). Onderstaande eisen gelden bovenop BIO waar van toepassing.

- **R-NIS2-01** **Bestuurlijke verantwoordelijkheid**: directie keurt risicomanagementmaatregelen goed, volgt training en is aansprakelijk voor naleving. `[NIS2]`
- **R-NIS2-02** **Risicomanagement** voor netwerk- en informatiesystemen op basis van een all-hazards-benadering, periodiek herzien. `[NIS2]`
- **R-NIS2-03** **Supply chain security**: leveranciersrisico-analyse, contractuele eisen (security, incident notificatie, audit-recht), SBOM voor kritieke componenten. `[NIS2]`
- **R-NIS2-04** **Meldplicht incidenten**: vroegsignalering binnen **24 uur**, incidentmelding binnen **72 uur**, eindrapport binnen **1 maand** richting CSIRT/toezichthouder. `[NIS2]`
- **R-NIS2-05** **Vulnerability disclosure**: gepubliceerd beleid en proces voor melden van kwetsbaarheden door derden. `[NIS2]`
- **R-NIS2-06** **Multifactor-authenticatie of continue authenticatie** voor alle toegang tot kritieke systemen. `[NIS2]`
- **R-NIS2-07** **Versleutelde communicatie** (incl. spraak/video/tekst waar relevant voor crisiscommunicatie). `[NIS2]`
- **R-NIS2-08** **Awareness en training** voor alle medewerkers en specifieke training voor bestuur. `[NIS2]`
- **R-NIS2-09** **Crisismanagement en business continuity** afgestemd met sectorale CSIRT en oefeningen met ketenpartners. `[NIS2]`
- **R-NIS2-10** **Effectiviteitsmeting** van cybersecurity-maatregelen via KPI's en periodieke assessments. `[NIS2]`

---

## 6. Data governance, kwaliteit en metadata

- **R-GOV-01** **Data ownership en stewardship** zijn per data product belegd; rollen vastgelegd (eigenaar, steward, custodian). `[NORA] [AVG] [BIO]`
- **R-GOV-02** **Data catalog** bevat technische én businessmetadata, classificatie, eigenaar, doel, bewaartermijn, kwaliteit en lineage. `[NORA] [AVG]`
- **R-GOV-03** **Data lineage** is end-to-end zichtbaar (bron → transformatie → consumptie) en machine-leesbaar (bijv. OpenLineage). `[NORA] [AVG]`
- **R-GOV-04** **Datakwaliteit**: dimensies (volledigheid, juistheid, tijdigheid, consistentie, uniciteit) met SLO's, tests in pipelines en dashboards. `[NORA]`
- **R-GOV-05** **Master data management** voor kerngegevens (klant/burger, product, locatie) met gouden record en match/merge-regels. `[NORA]`
- **R-GOV-06** **Policy-as-code**: toegangs-, classificatie- en bewaarbeleid afdwingbaar in pipelines (bijv. via OPA, Unity Catalog, Purview). `[BIO] [AVG]`
- **R-GOV-07** **Data contracts** tussen producenten en consumenten met schema, SLA en breaking-change-beleid. `[NORA]`

---

## 7. Functionele platformvereisten

### 7.1 Ingestie
- **R-FUN-01** Ondersteuning voor **batch, micro-batch en streaming** ingestie (CDC, Kafka, REST/SFTP/JDBC).
- **R-FUN-02** **Schema-validatie en evolutie** bij ingestie; afwijkingen worden gequarantaineerd en gerapporteerd.
- **R-FUN-03** **PII-detectie** bij ingestie met automatische tagging en routering naar versleutelde zones. `[AVG]`

### 7.2 Opslag en verwerking
- **R-FUN-04** **Lakehouse-architectuur** met medallion-zones (bronze/silver/gold) of vergelijkbaar; ACID-transacties op tabel-niveau.
- **R-FUN-05** **Scheiding compute en storage**, elastisch schaalbaar; multi-tenant isolatie via workspaces/projects.
- **R-FUN-06** **Time travel / versionering** op tabellen voor auditeerbaarheid en herstel. `[BIO]`

### 7.3 Analytics, BI en AI/ML
- **R-FUN-07** **Self-service BI** met semantische laag, gecertificeerde datasets en gecontroleerde publicatie.
- **R-FUN-08** **MLOps**: model registry, feature store, versioning, monitoring (drift, bias, performance), reproduceerbare pipelines.
- **R-FUN-09** **Verklaarbaarheid en bias-toetsing** voor modellen; documentatie via model cards. `[AVG]`
- **R-FUN-10** Aansluiting op **AI Act**-vereisten waar van toepassing (risicoclassificatie, logging, menselijk toezicht).

### 7.4 Integratie
- **R-FUN-11** **API-management** met authenticatie, rate limiting, throttling, audit en developer portal.
- **R-FUN-12** **Event-gedreven architectuur** met schema registry en dead-letter handling.

---

## 8. Niet-functionele vereisten

- **R-NF-01** **Beschikbaarheid** per dienst gespecificeerd (bijv. 99,9%) met SLO's, error budget en multi-AZ deploy. `[BIO] [NIS2]`
- **R-NF-02** **Schaalbaarheid**: horizontaal schaalbaar; performance-eisen per workloadtype (interactief, batch, streaming).
- **R-NF-03** **Observability**: metrics, logs en traces gecorreleerd; dashboards per data product.
- **R-NF-04** **FinOps**: kostentoerekening per team/dataproduct, budgetten en alerts.
- **R-NF-05** **Duurzaamheid**: keuze voor groene regio's, monitoring van energieverbruik en footprint van workloads. `[NORA]`
- **R-NF-06** **Toegankelijkheid (WCAG 2.2 AA)** voor alle eindgebruikers-UI's. `[NORA]`
- **R-NF-07** **Documentatie en kennisborging** per component, inclusief runbooks en architecture decision records.

---

## 9. Compliance, audit en assurance

- **R-COMP-01** **Mapping tussen requirements en maatregelen** wordt actueel gehouden in een GRC-tool, met evidence per control.
- **R-COMP-02** **Periodieke pentests en red-team-oefeningen**, minimaal jaarlijks of bij grote wijzigingen. `[BIO] [NIS2]`
- **R-COMP-03** **Externe assurance** waar relevant (ISO 27001, SOC 2 Type II, ENSIA, NEN 7510 voor zorg).
- **R-COMP-04** **DPIA-, ISMS- en risicoregister-onderhoud** als doorlopend proces, niet als eenmalige exercitie. `[AVG] [BIO]`
- **R-COMP-05** **Toezichthouder-readiness**: dossiers voor AP, RDI/Agentschap Telecom, sectorale toezichthouders zijn op afroep beschikbaar. `[AVG] [NIS2]`

---

## 10. Aanbevolen vervolgstappen

1. **Scopebepaling**: vaststellen of de organisatie onder NIS2 valt (essentieel/belangrijk) en welke BIO-/sectorale baselines van toepassing zijn.
2. **Gap-analyse** tegen deze requirementslijst; per gap een eigenaar en planning.
3. **Reference architecture** opstellen en valideren tegen NORA-principes.
4. **Control library** opbouwen waarin elke requirement één-op-één gemapt is op technische maatregelen, processen en evidence.
5. **Roadmap** met quick wins (logging, MFA, classificatie, catalog) vóór langere trajecten (MDM, MLOps-volwassenheid, zero-trust).

---

*Dit document is een startpunt. Per organisatie en sector kunnen aanvullende kaders gelden (NEN 7510 zorg, DNB Good Practice financieel, eIDAS, AI Act, Wpg/WJSG, Archiefwet). Toets deze lijst altijd tegen de actuele teksten van de wetten en standaarden en stem af met privacy officer, CISO en juridische zaken.*
