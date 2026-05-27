# ADR-0006: Delta Lake gekozen voor déze reference implementation

| Status | **Geaccepteerd — overrides ADR-0002 default** |
|---|---|
| Datum | 2026-04-30 |
| Beslissers | Platform Architect (op verzoek opdrachtgever) |
| Gerelateerd | ADR-0001 (Stackable), **ADR-0002 (Iceberg vs Delta)** |

---

## Context

[ADR-0002](0002-iceberg-vs-delta.md) bepaalt na een 10-criteria-analyse dat
**Iceberg** de default is for the ODAP platform (eindscore 45 vs 37). De
analyse blijft inhoudelijk geldig.

Voor **deze** reference implementation heeft de opdrachtgever desondanks
gekozen voor **Delta Lake**. Deze ADR legt die keuze vast en documenteert hoe
de risico's uit ADR-0002 worden geadresseerd.

---

## Beslissing

**`platform.table_format = delta`** in `platform-config.yaml`.

De volledige format-abstractie zoals beschreven in ADR-0002 §
Implementatie-impact blijft van kracht. Switching terug naar Iceberg vergt
alleen:

1. `platform-config.yaml`: `table_format: iceberg`.
2. Trino-catalogs hertemplateren (`scripts/render-trino-catalogs.py`) en
   redeployen.
3. dbt-models opnieuw materialiseren (`make dbt-rebuild-all`).

Geen code-wijzigingen elders.

---

## Motivatie voor deze afwijking

De afwijking is een **bewuste implementatie-keuze**. Mogelijke achtergronden
(opdrachtgever-perspectief, niet exhaustief gevalideerd):

- Toekomstige ODAP platformkeuze leunt richting Microsoft Fabric of Databricks
  (waar Delta first-class is).
- Bestaande Spark-expertise in het team is sterker met Delta dan met Iceberg.
- Liquid Clustering / Change Data Feed worden expliciet gewenst voor
  cliëntscan-workloads.
- Praktische ervaring opdoen met Delta is een leerdoel van deze referentie.

Geen van deze redenen ontkracht ADR-0002. Ze verschuiven alleen de
afweging op één criterium.

---

## Risico's uit ADR-0002 — en hoe we ze adresseren

### R1: Stackable's Delta-support is minder rijp (C3 — score 2)

**Bewijs.** De Stackable-referentie-demo is op Iceberg gebouwd; er is geen
end-to-end Delta-demo. NiFi heeft geen native `PutDeltaLake`-processor.
Trino's Delta-catalog werkt, maar er is geen voorbeeld-stack.

**Mitigatie.**

- **Ingestion-pad herontwerpen**: NiFi schrijft niet rechtstreeks naar Delta;
  in plaats daarvan schrijft NiFi naar **Kafka**, en **Spark Structured
  Streaming** schrijft van Kafka naar Delta op MinIO. Dit pad is robuust en
  goed ondersteund (Delta-Spark connector is first-class).
- **Trino's Delta-catalog** wordt geconfigureerd with the `delta-lake`
  connector + Hive Metastore. Dit is een ondersteunde combinatie.
- **NiFi-templates voor Iceberg blijven bestaan** in
  `nifi-flows/templates/iceberg/` zodat een terug-switch direct mogelijk is.

### R2: Trino-integratie minder rijk dan voor Iceberg (C1 — score 3)

**Bewijs.** Geen native materialized views, beperktere schema-evolutie,
deletion vectors pas recent.

**Mitigatie.**

- We gebruiken **dbt-trino's `materialized='table'`** (atomic
  `CREATE OR REPLACE TABLE`) als default — werkt voor Delta én Iceberg
  zonder feature-verschil voor onze use cases.
- Geen Trino-MV in dit referentieplatform; waar caching nodig is, gebruiken
  we incremental dbt-models.
- Schema-evolutie blijft toegankelijk via Spark (`ALTER TABLE ... ADD
  COLUMN`); incompatible schema-changes worden gedaan via een
  re-materialization (acceptabel patroon op Delta).

### R3: Vendor-neutraliteit (C4 — score 3)

**Bewijs.** Delta-spec wordt grotendeels door Databricks aangedreven.

**Mitigatie.**

- We gebruiken **uitsluitend de open-source Delta-runtime**, geen Databricks-
  specifieke uitbreidingen (geen Photon, geen Liquid Clustering vóór de
  open-source-release-datum).
- Dependency op `delta-spark` en `delta-storage` (Linux Foundation) is
  Apache 2.0 en in alle Maven Central / pip mirrors beschikbaar.
- ADR-0002 herzien als Iceberg-governance verandert of als Delta-governance
  alsnog naar één partij verschuift (geen dichte coupling met Databricks
  product-roadmap).

### R4: Multi-engine interoperabiliteit (C5)

Op Trino + Spark werkt Delta direct. Voor Flink (toekomstig) is Iceberg
beter; mocht Flink in scope komen, dan is Delta UniForm de upgrade-route.

---

## Operationele consequenties

| Onderwerp | Aanpassing tov ADR-0002 baseline |
|---|---|
| Trino-catalog-template | `delta-lake` connector ipv `iceberg`; metastore-config identiek |
| dbt-macros | `table_format_properties()` retourneert Delta-properties (geen `partitioning` ARRAY-key — Delta gebruikt expliciete `PARTITIONED BY`) |
| Spark-jobs | `lakehouse_io.write_delta()` als default; reads via `format("delta")` |
| NiFi-flows | Default deploy: `templates/delta/` (NiFi → Kafka). `templates/iceberg/` als optie |
| Maintenance-DAG | Delta: `OPTIMIZE table_name ZORDER BY (col)` + `VACUUM table_name RETAIN 168 HOURS`. Iceberg: `expire_snapshots` + `rewrite_data_files`. Helper-functie kiest aan de hand van `TABLE_FORMAT` |
| OPA-policies | **Onveranderd** — formaat-onafhankelijk |
| Compliance-mapping | Onveranderd — alle R-* eisen worden door beide formaten gedekt |

---

## Herzien wanneer

- Stackable rolt een eerstelijns Delta-end-to-end-demo uit → ADR-0002 score
  C3 omhoog → blijft Delta een goede keuze.
- UWV kiest definitief voor sovereign cloud zonder Databricks- of
  Fabric-toekomst → reden om naar Iceberg te switchen krijgt meer gewicht.
- Performance-onderzoek wijst uit dat een feature van het ándere formaat
  doorslaggevend is voor platform workloads.

Plan een **6-maandelijkse review** van deze keuze, niet jaarlijks zoals
ADR-0002, omdat de override-status het kader minder stabiel maakt dan een
"native" default-keuze.
