# Achtergrondsamenvatting — vier referentiedocumenten

Deze samenvatting bundelt de kernpunten van de vier achtergronddocumenten
die de scope, kaders en technische blauwdruk van deze referentie-implementatie
bepalen. Elk document is op zichzelf leidend voor zijn deelgebied; deze
samenvatting verwijst terug per beslissing.

---

## 1. `requirements.md` — kaderbaseline

**Inhoud.** Generieke requirementsbaseline met circa 75 genummerde eisen,
gegroepeerd in:

- **NORA** (R-NORA-01..09) — open standaarden, modulariteit, FAIR, federatieve identiteit, semantische interoperabiliteit.
- **AVG** (R-AVG-01..15) — rechtmatigheid (art. 6/9), privacy by design (dataminimalisatie, doelbinding, pseudonimisering), bewaartermijnen, rechten van betrokkenen, inbreukmeldingen.
- **BIO/BIO2** (R-BIO-01..24) — ISMS, RBAC/ABAC, encryption at rest/in transit, column-/row-level security, netwerksegmentatie, hardening, secure SDLC, immutable backups.
- **NIS2** (R-NIS2-01..10) — bestuurlijke verantwoordelijkheid, supply chain security, 24-uurs vroegsignalering + 72-uurs incident report.
- **Governance** (R-GOV), **functioneel** (R-FUN), **niet-functioneel** (R-NF), **compliance/audit** (R-COMP).

**Implicatie voor de bouw.** Elke maatregel die hier geïmplementeerd wordt,
moet één-op-één traceerbaar zijn naar een R-* code. De
[compliance-mapping](compliance-mapping.md) is daarom een verplichte tabel,
géén optionele bijlage. De skeleton wordt in fase 0 opgezet en groeit per fase
mee.

---

## 2. `referentiearchitectuur-odap-data-analytics.md` — UWV-specifieke scope

**Inhoud.**

- 12 architectuurprincipes (P-01..12), waaronder *doelbinding by design*,
  *eenmalig vastleggen meervoudig hergebruiken*, *CGM is leidend*, *zero-trust /
  least privilege / just-in-time*, *pseudonimiseren tenzij*, *mens-in-de-lus
  voor impactvolle besluiten*, *ethiek vooraf*.
- Lakehouse met **medallion-zones** (bronze/silver/gold) plus aparte **Sensitive
  Vault** voor bijzondere persoonsgegevens (art. 9 AVG — gezondheid).
- **Data mesh** rond domeinen (WW, AG/WIA/Wajong/ZW, CRM, FEZ, Handhaving,
  Arbeidsmarkt) met centrale Data Office.
- **CGM** (Canoniek Gegevensmodel) als bindend datamodel; **FUGEM** per domein
  via verticale lineage.
- 10 uitgewerkte use cases (UC-01..UC-10), waaronder UC-02 (Wajong AI) als
  **hoog-risico AI Act**-systeem en UC-05 (cliënt 360°) waar
  doelbinding-policies kritiek zijn.
- Bijlage A: mapping use-cases ↔ wetten ↔ CGM ↔ AVG-grondslag.

**Implicatie voor de bouw.** De use-case specs in `docs/use-cases/` worden
**gedestilleerd uit hoofdstuk 8** van dit document (entiteiten, bronnen,
compliance-eisen, risico's). De CGM-glossary in OpenMetadata baseert op
**bijlage B**. Sensitive Vault wordt een **aparte Trino-catalog** (`sensitive`)
met striktere OPA-policies.

---

## 3. `odap-platform-mapping-research.md` — technische blauwdruk

**Inhoud.** Component-tot-component-mapping zonder overlap, geen gaten:

- **Stackable Data Platform 26.3** (operators) levert: NiFi (ingestion), Kafka
  (event backbone), Spark (batch + streaming), Hive Metastore (catalog
  backend), Trino (SQL engine), Airflow (orchestratie), Superset (BI), OPA
  (authorisatie), ZooKeeper, secret-/listener-/commons-operator.
- **dbt-trino** (Apache 2.0) levert de transformatielaag (staging/intermediate/marts).
- **OpenMetadata** levert catalog (technisch + business), classifications,
  glossary, lineage, data quality, profiler.

Per use case is genoteerd welk Stackable-component, welk dbt-model en welke
OpenMetadata-tag of -workflow nodig is. Compliance-mapping (kort) geeft per
eis (AVG/BIO/NIS2/AI Act/NORA) de concrete maatregel.

**Implicatie voor de bouw.** Deze mapping is leidend; afwijken vereist een ADR.
"Wie doet wat" is hier vastgelegd. De architectuur-overview in
[`docs/architecture.md`](architecture.md) is een schaal-aangepaste hertaling
van deze mapping naar onze k3d-context.

---

## 4. `odap-platform-adr-0002-iceberg-vs-delta.md` — tabelformaat-keuze

**Inhoud.** Expliciete afweging tussen Apache Iceberg en Delta Lake op tien
criteria. **Iceberg** wint op 6 punten (Trino-rijpheid, Stackable-demo-maturity,
vendor-neutraliteit ASF, multi-engine, sovereign-cloud-fit). **Delta** wint op
Spark-rijpheid en fabric/databricks-fit. Eindscore: Iceberg 45 vs Delta 37.
**Default = Iceberg.**

Belangrijk: de keuze is **structureel** maar reverseerbaar mits het platform
agnostisch genoeg gebouwd wordt. Concreet:

- Trino-catalogs per-formaat geconfigureerd (template-rendering).
- dbt: macro `table_format()` leest `var('table_format')` en kiest properties.
- Spark: `TABLE_FORMAT` env + helper `write_table()`.
- NiFi: twee parallelle template-sets.
- OPA: format-onafhankelijk (kijkt naar catalog/schema/table-namen).

**Implicatie voor de bouw.** Voor *deze* implementatie is via gebruikerskeuze
gekozen voor **Delta Lake** — zie [ADR-0006](adr/0006-delta-chosen-for-this-implementation.md).
De abstractie blijft volledig in stand zodat een latere switch werkbaar is.

---

## Samenvattende implicaties

1. **Eén bron van waarheid voor het tabelformaat.** `platform-config.yaml`
   bepaalt of Iceberg of Delta wordt gebruikt; geen hardcoded keuzes elders.
2. **Compliance-mapping** is een levend document, geen poster.
3. **CGM is dwingend** voor gold-modellen; afwijking vraagt waiver.
4. **Sensitive data** krijgt een eigen catalog en striktere OPA-policies.
5. **Mens-in-de-lus** is non-negotiable voor besluitvormingsondersteunende
   modellen (UC-02, UC-03).
6. **Stackable + dbt + OpenMetadata** is de spilarchitectuur — geen
   parallel-stacks, geen "zelf bouwen wat al opgelost is".
