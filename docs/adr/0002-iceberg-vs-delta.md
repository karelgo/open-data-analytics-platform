# ADR-0002: Iceberg of Delta Lake als tabelformaat

> **Noot:** Dit ADR is de generieke afweging tussen Apache Iceberg en
> Delta Lake. Voor déze referentie-implementatie is in
> [ADR-0006](0006-delta-chosen-for-this-implementation.md) gekozen voor
> Delta Lake — een afwijking van de hieronder voorgestelde default Iceberg.

---

| Status | **Voorgesteld — default Iceberg, herzienbaar** |
|---|---|
| Datum | 2026-04-30 |
| Beslissers | Platform Architect, Data Office, CISO |
| Gerelateerd | ADR-0001 (Stackable als basis), ADR-0005 (dbt-trino), ADR-0006 (Delta-keuze deze implementatie) |

---

## Context

Het ODAP platform gebruikt een **lakehouse**-architectuur. Daarbij is een **open table format** essentieel: het verzorgt ACID-transacties, schema-evolutie, time travel, partition pruning en upserts bovenop Parquet-bestanden in object storage.

Twee serieuze open-source kandidaten:

- **Apache Iceberg** (Apache Software Foundation, sinds 2018)
- **Delta Lake** (Linux Foundation sinds 2022, ontwikkeld door Databricks sinds 2017)

Beide formaten ondersteunen Parquet, ACID-transacties, schema-evolutie, time travel, en de meeste compute-engines (Spark, Trino, Flink). Het verschil zit in **rijpheid per engine, ecosysteem-positie, vendor-neutraliteit en operationele features**.

Deze keuze is structureel: migreren is mogelijk maar duur. Daarom een expliciete afweging.

---

## Beoordelingscriteria

| # | Criterium | Gewicht |
|---|---|---|
| C1 | Rijpheid van Trino-integratie (primaire query-engine) | Hoog |
| C2 | Rijpheid van Spark-integratie (primaire processing-engine) | Hoog |
| C3 | Stackable-ondersteuning out-of-the-box (referentie-demo, operator-config) | Hoog |
| C4 | Vendor-neutraliteit / governance van het project (NORA-principe) | Hoog |
| C5 | Multi-engine interoperabiliteit (toekomstbestendigheid) | Middel |
| C6 | Operationele features (compaction, partition evolution, branching, MV) | Middel |
| C7 | Performance op platform workloads (cliëntscans, tijdreeksen) | Middel |
| C8 | Ecosysteem (catalogs, tools, community-momentum) | Middel |
| C9 | dbt-trino-compatibiliteit | Hoog |
| C10 | Toekomstige cloud-keuze (Azure Fabric, Databricks, AWS, sovereign) | Hoog |

---

## Vergelijking

### C1 — Trino-integratie

**Iceberg (winnaar).** Trino's Iceberg-connector is uitgebreid en volwassen: materialized views, hidden partitioning, partition evolution zonder rewrite, branching/tagging (in ontwikkeling), `OPTIMIZE`, `expire_snapshots`, `remove_orphan_files` als native procedures.

**Delta.** Trino-connector is functioneel maar minder rijk: geen native materialized views (alleen via Iceberg-storage onder de motorkap), beperkte schemaevolutie, deletion vectors pas recent ondersteund. Werkt wel goed voor read-heavy workloads.

### C2 — Spark-integratie

**Delta (winnaar).** Eerstelijns op Databricks Spark; alle features (liquid clustering, deletion vectors, change data feed, generated columns) komen daar als eerste. Open-source Spark heeft alle features ook, maar soms met een release-vertraging.

**Iceberg.** Werkt goed met Apache Spark via `iceberg-spark-runtime`. Branching/tagging alleen via Spark, niet (nog) in Trino.

### C3 — Stackable-ondersteuning

**Iceberg (duidelijke winnaar).** De Stackable-referentie-demo `data-lakehouse-iceberg-trino-spark` is volledig op Iceberg gebouwd: NiFi heeft `PutIceberg`-processor, Spark Structured Streaming `MERGE INTO Iceberg`, Trino-catalog `iceberg`, complete maintenance-procedures. Documentatie en troubleshooting zijn op Iceberg geschreven.

**Delta.** Stackable Trino heeft wel een Delta Lake-catalog (`trinocatalog-delta-lake.yaml`), maar geen end-to-end demo. NiFi heeft geen native Delta-processor; Delta-writes via Spark werken, maar zijn niet pre-geconfigureerd. Te bouwen, maar de eerste 4–8 weken zijn moeilijker.

### C4 — Vendor-neutraliteit

**Iceberg (winnaar).** Apache Software Foundation, brede comité-governance (Netflix, Apple, AWS, Snowflake, Salesforce, Cloudera, Tabular). Specificatie staat los van een commerciële sponsor.

**Delta.** Linux Foundation sinds 2022, maar in de praktijk blijft Databricks de motor. Delta-spec ontwikkelt grotendeels via Databricks-prioriteiten. Voor een overheid is dat een politieke afweging: de standaard is open, de roadmap minder.

### C5 — Multi-engine interoperabiliteit

**Iceberg.** Native ondersteuning in Trino, Spark, Flink, Dremio, Snowflake, Athena, BigQuery, Starburst, Impala.

**Delta.** Native in Spark, goed in Trino, beperkt in Flink. **Delta UniForm** (sinds 2023) genereert Iceberg-metadata bovenop Delta-tabellen waardoor Iceberg-clients ze kunnen lezen — dit verkleint het verschil aanzienlijk, maar voegt complexiteit toe.

### C6 — Operationele features

| Feature | Iceberg | Delta |
|---|---|---|
| ACID transactions | OK | OK |
| Schema evolution | OK (met partition evolution) | OK (geen partition evolution) |
| Time travel | OK (snapshots) | OK (versions) |
| Hidden partitioning | OK | nee (vereist generated columns) |
| Z-ordering / clustering | Via Spark sort | OK (Z-order, Liquid Clustering) |
| Branching / tagging | OK (Spark, Trino in ontwikkeling) | nee |
| Materialized views in Trino | OK native | nee (omweg via Iceberg) |
| Deletion vectors | OK (v3 spec) | OK |
| Change Data Feed | Via snapshots + diff | OK native |

Voor UWV (veel correctie-runs op claimbeoordelingen, audits, herbeoordelingen) zijn **branching/tagging** en **partition evolution** nuttige features die alleen Iceberg biedt. **Liquid clustering** van Delta is interessant voor cliëntscans, maar niet kritisch.

### C7 — Performance op platform workloads

Voor de meeste platform workloads (analytische queries, dashboards, dbt-runs) is het verschil **klein in de praktijk**. Beide formaten profiteren van vergelijkbare optimalisaties (file pruning, statistics).

- Cliënt-360 lookups: Iceberg met hidden partitioning op `bsn_hash_bucket` werkt goed; Delta vereist Liquid Clustering.
- Tijdreeksen (audit-logs, schadelast): beide hebben sterke partition pruning op datum.
- Veel-update-workloads (uitkeringen-status, dossierstatus): Delta merge is iets sneller in Spark; Iceberg `MERGE INTO` heeft ingehaald.

Geen duidelijke winnaar zonder benchmark op echte ODAP data.

### C8 — Ecosysteem

**Beide sterk.** Iceberg heeft REST Catalog, Polaris, Nessie, Tabular. Delta heeft Unity Catalog, Delta Sharing. Voor open source en multi-engine is Iceberg's ecosysteem op dit moment iets diverser.

### C9 — dbt-trino-compatibiliteit

**Beide ondersteund.** dbt-trino werkt naadloos met Iceberg (Materialized View, MERGE incremental strategy, atomic CREATE OR REPLACE TABLE) en met Delta (vergelijkbare features). Geen blokker.

### C10 — Toekomstige cloud-keuze

- **Microsoft Fabric / OneLake**: native Delta. Iceberg via UniForm of read-only Iceberg shortcut.
- **Databricks**: native Delta. Iceberg via UniForm.
- **AWS**: beide, Athena ondersteunt beide; Iceberg sinds 2022.
- **Azure Synapse**: Delta beter geïntegreerd; Iceberg via OSS Spark.
- **On-prem / sovereign cloud (Stackable, OpenShift, IONOS, etc.)**: beide werken; Iceberg heeft sterkere out-of-the-box experience zonder Databricks.

**Voor UWV specifiek:** geen besluit genomen over hyperscaler. Sovereign cloud (Leonardo) en on-prem zijn realistische scenario's. Daar is Iceberg de natuurlijkere keuze.

---

## Score (subjectief, 1=slecht, 5=uitstekend)

| Criterium | Iceberg | Delta |
|---|---|---|
| C1 Trino | 5 | 3 |
| C2 Spark | 4 | 5 |
| C3 Stackable | 5 | 2 |
| C4 Vendor-neutraal | 5 | 3 |
| C5 Multi-engine | 5 | 4 (met UniForm) |
| C6 Ops features | 4 | 4 |
| C7 Performance | 4 | 4 |
| C8 Ecosysteem | 4 | 4 |
| C9 dbt-trino | 5 | 5 |
| C10 Cloud-keuze | 4 (sovereign + AWS) | 3 (Azure/Databricks-specifiek) |
| **Totaal** | **45** | **37** |

---

## Beslissing

**Default tabelformaat = Apache Iceberg.**

Belangrijkste redenen:
1. Stackable's referentie-demo en operator-features zijn op Iceberg gebouwd → meetbaar minder bouw- en onderhoudsrisico.
2. Trino is de centrale query-engine; Iceberg-integratie is daar het meest volwassen.
3. Past bij NORA-principe vendor-neutraliteit; Iceberg is breed gegoverneerd via ASF.
4. Sovereign cloud / on-prem als realistische deployment-doelen; Iceberg werkt daar zonder Databricks-afhankelijkheid.

> **Voor déze implementatie** is desondanks Delta Lake gekozen — zie
> [ADR-0006](0006-delta-chosen-for-this-implementation.md) voor de redenen
> en de mitigaties die de ADR-0002-risico's adresseren.

---

## Onder welke omstandigheden herzien

Maak deze keuze **expliciet ongedaan** als:

1. **UWV kiest strategisch voor Microsoft Fabric of Databricks** als primaire platform. → Migreer naar Delta of voeg Delta UniForm toe.
2. **Realistisch performance-onderzoek wijst uit** dat Liquid Clustering aantoonbaar betere latency geeft op cliënt-360-workloads dan Iceberg hidden partitioning + bucketing. → Heroverweeg.
3. **Stackable rolt een end-to-end Delta-demo uit** met vergelijkbare maturity als de Iceberg-demo. → Herzie C3.
4. **Apache Iceberg-governance verschuift** richting één commerciële partij (zoals destijds bij Hadoop). → Herzie C4.

Plan een herziening **één jaar na go-live** of bij een van bovenstaande triggers.

---

## Implementatie-impact

Het platform moet **agnostisch genoeg gebouwd worden** dat een latere switch werkbaar is. Concreet:

- Trino-catalogs zijn **per-formaat** geconfigureerd (`iceberg_*` of `delta_*`); de catalogs zijn als losse YAML-bestanden te swappen.
- dbt models gebruiken een **`+materialized` config in `dbt_project.yml`** met een variabele:
  ```yaml
  vars:
    table_format: iceberg   # iceberg | delta
  models:
    +on_table_exists: replace
  ```
  Macros lezen `var('table_format')` en zetten de juiste `properties{}` block.
- Spark-jobs lezen `TABLE_FORMAT` uit env; schrijfcode is geabstraheerd in een helper `write_table(df, name, mode)`.
- NiFi-flows hebben twee varianten (`PutIceberg` en `PutDeltaLake`). Default deployen we Iceberg, Delta-flows blijven als template in repo.
- OPA-policies zijn **formaat-onafhankelijk** (kijken naar catalog/schema/table naam, niet naar onderliggend formaat).

Met deze abstractie kost een migratie weken, niet maanden.

---

## Niet gekozen alternatieven

- **Apache Hudi.** Goed voor incremental processing, maar minder volwassen Trino-integratie, minder Stackable-support, kleiner ecosysteem.
- **Apache Paimon.** Veelbelovend voor streaming + lakehouse, maar te jong voor productie-overheid.
- **Plain Parquet (geen tabelformaat).** Geen ACID, geen schema-evolutie, geen time travel. Niet acceptabel voor compliance-eisen (audit, correctie, retentie).

---

## Referenties

- Apache Iceberg: https://iceberg.apache.org
- Delta Lake: https://delta.io
- Stackable lakehouse demo: https://docs.stackable.tech/home/stable/demos/data-lakehouse-iceberg-trino-spark/
- Trino Iceberg connector: https://trino.io/docs/current/connector/iceberg.html
- Trino Delta connector: https://trino.io/docs/current/connector/delta-lake.html
- Delta UniForm: https://docs.delta.io/latest/delta-uniform.html
- dbt-trino Iceberg: https://docs.getdbt.com/reference/resource-configs/trino-configs

---

*Deze ADR is opzettelijk uitgebreid omdat de keuze structureel is. Toekomstige aanpassingen van deze ADR vereisen instemming van Platform Architect én Data Office.*
