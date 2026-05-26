# Stackable + dbt + OpenMetadata — Mapping op UWV Referentiearchitectuur

**Doel:** alle drie componenten technisch en functioneel mappen op de eerder opgestelde UWV-referentiearchitectuur, en een ready-to-use master agent prompt opstellen voor Claude Code.

---

## 1. Onderzoeksbevindingen

### 1.1 Stackable Data Platform (SDP) 26.3

Stackable levert **Kubernetes-operators** voor open-source data-componenten. Geen vendor lock-in, alle componenten zijn upstream Apache/CNCF-projecten met uniforme operator-conventies (Stacklet, AuthenticationClass, S3Connection, ListenerClass, SecretClass).

**Beschikbare product-operators:**

| Component | Rol in lakehouse | Inzet voor UWV |
|---|---|---|
| **Apache NiFi** | Flow-based ingestion, supports Iceberg writes | SuwiML-adapters, CDC, batch ingest, PII-tagging at ingest |
| **Apache Kafka** | Event streaming backbone | Event-driven backbone tussen domeinen |
| **Apache Spark on K8s** | Batch + structured streaming | Kafka→Iceberg, ML training, batch joins |
| **Apache Hive Metastore** | Metadata-store voor Iceberg/Hive catalogs | **Verplichte** catalog backend voor Trino+Iceberg |
| **Apache HDFS** | Distributed FS | Optioneel; we gebruiken liever S3/MinIO |
| **Trino** | Distributed SQL engine, Iceberg/Delta/Hive catalogs, OPA-authorizer | Centrale query laag voor BI, dbt, gegevensdiensten |
| **Apache Airflow** | Orchestratie, K8s executor | dbt runs, OpenMetadata ingestion, Iceberg-onderhoud |
| **Apache Superset** | BI-tool | Dashboards (UC-01, UC-06) |
| **OpenSearch** | Search + vector | Optioneel: zoeken in dossiers, RAG voor cliëntenservice |
| **Apache Druid** | Real-time OLAP | Optioneel: real-time KPI-streams |
| **Apache HBase** | Wide-column NoSQL | Optioneel: low-latency lookups |
| **Apache ZooKeeper** | Coordination | Vereist voor Kafka, HBase |

**Cross-cutting / interne operators:**

| Component | Doel | Use voor UWV |
|---|---|---|
| **OpenPolicyAgent (OPA)** | Policy-as-code (Rego) | RBAC + ABAC + column masking + row filters voor Trino; doelbinding-policies; integratie met Druid en Kafka authz |
| **Secret Operator** | TLS-certs en secrets, automatic renewal, cert-manager-integratie | TLS overal, sleutel-rotatie |
| **Listener Operator** | Service exposure, stable out-of-cluster access | Beheerd via ListenerClass per dienst |
| **Commons Operator** | Gedeelde CRDs (AuthenticationClass, S3Connection, S3Bucket) | Centrale auth + S3-config |

**Belangrijke OPA-features (Trino 438+):**

- **Allow/deny per resource** (catalog/schema/table/column).
- **Row filtering**: Rego retourneert WHERE-clauses per rol/groep.
- **Column masking**: Rego retourneert SQL-expressies (NULL, `'****' || substring(...)`, etc.) per kolom.
- **Batched evaluation** voor performance.
- **Bundles via ConfigMap** met label `opa.stackable.tech/bundle: "true"`.

**Authenticatie:**

- **AuthenticationClass** CRD; ondersteunt OIDC (ADR032), LDAP, TLS-certs.
- Native Keycloak-integratie (zie `jupyterhub-keycloak` demo).

**Reference-demo `data-lakehouse-iceberg-trino-spark`:** complete blauwdruk met NiFi → Kafka → Spark Structured Streaming → Iceberg op MinIO, Hive metastore als Iceberg-catalog, Trino + OPA + Superset. Iceberg-`MERGE INTO` voor upserts, plus `expire_snapshots` / `remove_orphan_files` / `rewrite_data_files` voor onderhoud.

**Tools:** `stackablectl` (CLI, kan operators én demo's installeren), Stackable Cockpit (UI).

### 1.2 dbt-core + dbt-trino adapter

**dbt-trino**: officiële, open-source adapter (Apache 2.0). Werkt naadloos met Trino's Iceberg-connector.

**Belangrijke kenmerken voor UWV:**

- **Materializations**: `view`, `table`, `incremental`, `materialized_view` (Trino 431+ ondersteunt CREATE OR REPLACE TABLE atomisch).
- **Iceberg-specifieke configuratie**:
  ```jinja
  {{ config(
      materialized='table',
      properties={
          'format': "'PARQUET'",
          'partitioning': "ARRAY['day(timestamp)']"
      }
  ) }}
  ```
- **Incremental strategies**: `append`, `delete+insert`, `merge` (gebruikt `MERGE INTO` van Iceberg).
- **`on_table_exists`**: `replace` (atomisch via `CREATE OR REPLACE TABLE`), `rename`, `drop`, `skip`.
- **Tests**: built-in (`unique`, `not_null`, `accepted_values`, `relationships`) + singular tests voor UWV-business rules.
- **Snapshots**: voor SCD-tracking, bv. wijzigingen in dossierstatus.
- **dbt-utils + dbt-expectations**: kant-en-klare test-libraries.
- **Docs**: `dbt docs generate` produceert `manifest.json`, `catalog.json`, `run_results.json` — exact wat OpenMetadata nodig heeft.

**platform mapping**: dbt wordt de **transformation-laag tussen bronze en silver/gold**. CGM-conformiteit wordt afgedwongen via dbt-tests + naming-conventies + tags.

### 1.3 OpenMetadata 1.12+

**Architectuur:**

- Backend: Java/Dropwizard + MySQL/PostgreSQL + OpenSearch/Elasticsearch.
- **Kubernetes-deployment**: officiële Helm chart `openmetadata-helm-charts`. Sinds 1.12 ook **eigen Kubernetes Orchestrator** (alternatief voor Airflow voor metadata-ingestion).
- **Ingestion Framework**: Python-based, draait extern (Airflow, K8s, lokaal, GitHub Actions).

**Relevante connectors voor UWV:**

| Bron | Wat wordt opgehaald |
|---|---|
| **Trino** | Schemas, tables, views, columns, types, owners, descriptions, **lineage** (uit query history), **column-level lineage**, **data profiling** (statistieken), **data quality tests**, **tags** |
| **dbt** | Models (incl. SQL), test-resultaten, ownership, descriptions, lineage uit `ref()`, tags, glossary, domains, custom properties |
| **Airflow** | DAGs, runs, task-lineage |
| **Superset** | Dashboards, charts, lineage naar onderliggende datasets |
| **Kafka** | Topics, schemas |

**Governance-features die UWV nodig heeft:**

- **Classifications** (PII, vertrouwelijkheid, BIO-classificatie, gezondheidsgegevens art. 9 AVG).
- **Glossary** met **business terms** — kan exacte CGM/FUGEM-termen herbergen.
- **Tags** worden via API gepushed of via auto-classification.
- **Domains / Data Products** — perfect voor UWV's WW/AG/CRM/FEZ-domeinen.
- **Reverse Metadata** (Collate/enterprise; community heeft Trino metadata exporter sinds #25970): tags terug naar Trino → kan OPA-policies voeden.
- **Data lineage**: tabel- én kolomniveau, end-to-end.
- **Auto-Classification**: automatische detectie van BSN-achtige patronen; aan te vullen met custom rules of LLM-driven tagging.
- **MCP Server**: ondersteunt agent-based interactie met catalog (mogelijk relevant voor toekomst).

**Cruciale flow voor lineage:**

1. dbt run → `manifest.json`/`catalog.json`/`run_results.json` → uploaden naar S3/MinIO.
2. OpenMetadata "Database Service" voor Trino → ingestie van schemas/tables.
3. OpenMetadata "dbt Workflow" gekoppeld aan Trino-service → lineage + descriptions.
4. Trino query-history → lineage-workflow → kolom-niveau lineage.

### 1.4 Integratie-overlap

| Capability | Stackable | dbt | OpenMetadata | Verantwoordelijkheid |
|---|---|---|---|---|
| **Storage** | MinIO + Iceberg | – | – | Stackable |
| **Compute** | Spark, Trino | – | – | Stackable |
| **Ingestion (raw)** | NiFi, Kafka, Spark | – | – | Stackable |
| **Transformation** | – | dbt | – | dbt |
| **Schemas/tables creation** | – | dbt (CREATE) | – | dbt |
| **Authz** | OPA (Stackable) | – | (input voor OPA) | Stackable + OpenMetadata |
| **AuthN** | AuthenticationClass + Keycloak | – | – | Stackable |
| **Catalog (technical)** | Hive Metastore (voor Iceberg) | – | – | Stackable |
| **Catalog (business)** | – | (schema.yml descriptions) | OpenMetadata | OpenMetadata |
| **Lineage (technical)** | – | (manifest.json) | OpenMetadata | OpenMetadata |
| **Tests/DQ** | – | dbt tests | OpenMetadata DQ + Profiler | dbt + OpenMetadata |
| **Glossary / CGM-mapping** | – | – | OpenMetadata | OpenMetadata |
| **Tags / Classifications** | – | (via meta) | OpenMetadata | OpenMetadata |
| **Doelbinding policies** | OPA Rego | – | (tags voeden policies) | Stackable + OpenMetadata |
| **Orchestratie** | Airflow | – | – | Stackable Airflow |
| **Observability** | Vector + Prometheus + OpenTelemetry | – | OpenMetadata observability | Stackable + OpenMetadata |
| **BI** | Superset | – | – | Stackable |
| **Secrets/TLS** | Secret-operator + cert-manager | – | – | Stackable |

---

## 2. Doelarchitectuur — concrete componenten

```
┌───────────────────────────────────────────────────────────────────────────┐
│ KUBERNETES CLUSTER (NL/EU sovereign)                                     │
│                                                                          │
│  ┌─── Bron-mocks ────────────────────────────────────────────────────┐   │
│  │ Synthetische data-generators (Python jobs):                       │   │
│  │ • Polisadministratie • WIA • Wajong • WW • CRM • FEZ              │   │
│  │ → REST/CSV/JDBC, gepushed naar NiFi of S3                         │   │
│  └───────────────────────────┬───────────────────────────────────────┘   │
│                              │                                           │
│  ┌───────────────────────────▼───────────────────────────────────────┐   │
│  │ Apache NiFi  (Stackable NiFiCluster)                              │   │
│  │ • SuwiML/REST/JDBC adapters                                       │   │
│  │ • Auto-PII-detectie + tagging via UpdateAttribute                 │   │
│  │ • PutIceberg → bronze (direct) OF PublishKafka → streaming        │   │
│  └─────────────────┬─────────────────────────────┬───────────────────┘   │
│                    │ batch                       │ streaming             │
│                    │                             ▼                       │
│                    │           ┌─────────────────────────────────────┐   │
│                    │           │ Apache Kafka (Stackable KafkaCluster)│   │
│                    │           │ Topics: uwv.{domain}.{event}        │   │
│                    │           └────────────┬────────────────────────┘   │
│                    │                        │                            │
│                    │                        ▼                            │
│                    │           ┌─────────────────────────────────────┐   │
│                    │           │ Spark Structured Streaming         │   │
│                    │           │ (Stackable SparkApplication)        │   │
│                    │           │ Kafka → Iceberg bronze (MERGE INTO) │   │
│                    │           └────────────┬────────────────────────┘   │
│                    │                        │                            │
│                    └────────────┬───────────┘                            │
│                                 │                                        │
│  ┌──────────────────────────────▼─────────────────────────────────────┐   │
│  │ MinIO (S3-compatible)                                              │   │
│  │ Buckets:                                                           │   │
│  │   odap-bronze   • odap-silver   • odap-gold                           │   │
│  │   sensitive (medisch, art. 9 AVG)                              │   │
│  │   odap-staging  • odap-checkpoints                                   │   │
│  │ Iceberg-tabellen, partitioned by event_date, etc.                  │   │
│  └──────────────────────────────┬─────────────────────────────────────┘   │
│                                 │                                        │
│  ┌──────────────────────────────▼─────────────────────────────────────┐   │
│  │ Hive Metastore (Stackable HiveCluster) + PostgreSQL                │   │
│  │ Iceberg-catalog backend                                            │   │
│  └──────────────────────────────┬─────────────────────────────────────┘   │
│                                 │                                        │
│  ┌──────────────────────────────▼─────────────────────────────────────┐   │
│  │ Trino (Stackable TrinoCluster)                                     │   │
│  │ Catalogs:                                                          │   │
│  │   • iceberg_bronze    • iceberg_silver    • iceberg_gold           │   │
│  │   • iceberg_sensitive (apart, met striktere OPA-policies)          │   │
│  │ Auth:                                                              │   │
│  │   • OIDC via Keycloak (AuthenticationClass)                        │   │
│  │   • OPA-authorizer met row filters + column masking                │   │
│  │ Coordinator + worker pools, fault-tolerant execution               │   │
│  └─────┬──────────────────────────────┬──────────────────────────┬────┘   │
│        │                              │                          │        │
│        ▼                              ▼                          ▼        │
│  ┌───────────────┐            ┌──────────────────┐      ┌───────────────┐│
│  │ dbt-core      │            │ Apache Superset  │      │ OpenMetadata  ││
│  │ (in Airflow   │            │ (Stackable       │      │ (eigen Helm)  ││
│  │  K8s pods)    │            │  SupersetCluster)│      │ + ingestion   ││
│  │               │            │                  │      │   workflows   ││
│  │ profiles.yml  │            │ Dashboards per   │      │               ││
│  │ → trino://... │            │ UC               │      │ Connectors:   ││
│  │               │            │ OIDC SSO         │      │ • Trino       ││
│  │ Models:       │            │ Row-level        │      │ • dbt         ││
│  │ - staging/    │            │ security via     │      │ • Superset    ││
│  │ - intermediate│            │ Trino+OPA        │      │ • Airflow     ││
│  │ - marts/uc01..│            │                  │      │ • Kafka       ││
│  │              │            │                  │      │               ││
│  └──────┬────────┘            └──────────────────┘      └──────┬────────┘│
│         │                                                       │        │
│         │ manifest.json + catalog.json + run_results.json       │        │
│         │ uploaded to s3://odap-meta/dbt/                        │        │
│         └───────────────────────────────────────────────────────┘        │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │ Apache Airflow (Stackable AirflowCluster) — orchestratie          │   │
│  │ DAGs:                                                             │   │
│  │  • dbt_run_<domain>     (uses KubernetesPodOperator → dbt-trino)  │   │
│  │  • iceberg_maintenance  (compaction + snapshot expiry)            │   │
│  │  • om_ingest_trino      (OpenMetadata metadata-rest workflow)     │   │
│  │  • om_ingest_dbt        (uploads + ingest manifest)               │   │
│  │  • om_lineage_trino     (column-level lineage from query history) │   │
│  │  • spark_streaming_*    (long-running Structured Streaming)       │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─── Cross-cutting ─────────────────────────────────────────────────┐   │
│  │ • Keycloak (OIDC) — federated identity, mock SUWI-rollen         │   │
│  │ • OPA (Stackable OpaCluster)                                      │   │
│  │   - bundle: trino-base + purpose-limitation + platform-roles + masks      │   │
│  │ • Secret Operator + cert-manager — TLS rotation                   │   │
│  │ • Listener Operator — service exposure                            │   │
│  │ • Vector — log aggregation (Stackable native)                     │   │
│  │ • Prometheus + Grafana — metrics                                  │   │
│  │ • OpenTelemetry collector (Trino, OPA support OpenTelemetry)      │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. UWV-specifieke integratiepunten (mapping use cases)

| UC | Stackable | dbt | OpenMetadata |
|---|---|---|---|
| **UC-01 WIA Funnel** | NiFi WIA-mock → Kafka `uwv.wia.aanvraag` → Spark → bronze.wia_aanvraag; Trino voor query | `staging/wia/__sources.yml` → `marts/uc01_wia_funnel/wia_funnel_daily.sql` (incremental, partition by dag); tests: `not_null(aanvraag_id)`, `unique(aanvraag_id)`, `accepted_values(status)` | Tag: `domain.AG`, `wet.WIA`; Glossary terms uit CGM (`Aanvraag`, `Beoordeling`); dashboard certificering via OM |
| **UC-02 Wajong AI** | SparkApplication ML-training; SparkConnect voor inference; Trino voor feature serving | `staging/wajong/`, `intermediate/wajong/features.sql`, `marts/uc02_wajong/risk_features_v1.sql` met `meta: {tier: hoog_risico, dpia: required}` | Classification: `PII.Sensitive`, `Health.Article9`; **hoog-risico AI**-tag; lineage feature → model |
| **UC-03 WW risk** | Spark Streaming Kafka→Iceberg silver | `marts/uc03_ww/verwijtbaar_signalen.sql` (incremental merge op `aanvraag_id`); singular test `dbt_test_no_features_in_protected_columns` | Tag: `algorithm.registered`; mock-link naar UWV algoritmeregister-id |
| **UC-04 Proactieve TW** | Trino-only (regel-gebaseerd, geen ML); Airflow CronDAG | `marts/uc04_tw/tw_eligibility.sql` met expliciete WHERE-clausules op grondslag; tests verplicht | Tag: `legal_basis.Wet_proactieve_dienstverlening`; geen profilering-tag |
| **UC-05 Cliënt 360** | Trino semantic layer; API via Trino REST | `marts/uc05_client_360/client_overview.sql` (view, column-level masked) | **Doelbinding tag per kolom**; OPA-mask leest deze tag uit OM via reverse-metadata |
| **UC-06 Schadelast** | Trino + Spark MLlib voor tijdreeks | `marts/uc06_lastprognose/uitkeringslast_5y.sql` (geaggregeerd, geen PII) | Geen PII; openbaar dashboard |
| **UC-07 DQ Polisadm.** | NiFi-validatie + Spark | `tests/polisadm/test_iban_format.sql`, `test_bsn_checksum.sql`, `models/staging/polisadm/__schema.yml` met dbt-expectations | Profiler results in OM; alerts op DQ-drempels |
| **UC-08 SMZ-planning** | Trino + custom optimizer (Python) | `marts/uc08_smz/capaciteit_dagelijks.sql` | Tag: `internal_only` |
| **UC-09 Re-int effectmeting** | Spark sandbox; gepseudonimiseerde panels | `marts/uc09_reint_panels/effect_panel.sql` | Sandbox-tag; pseudo-IDs verplicht |
| **UC-10 Mijn Gegevensdiensten** | Trino REST API + OPA per afnemer | `marts/uc10_gegevensdiensten/api_polisadm_gemeente.sql` (view per afnemer met OPA-rol) | Doel per afnemer als classificatie, OPA leest dit |

---

## 4. Compliance-mapping (kort)

| Eis | Implementatie |
|---|---|
| **AVG doelbinding** | OPA Rego policies + OM classifications per kolom; Trino weigert query als doelcode niet matcht |
| **AVG dataminimalisatie** | dbt models projecteren expliciet, OPA column masks default-deny op gevoelige kolommen |
| **AVG art. 9 (gezondheid)** | Aparte `iceberg_sensitive` catalog; OPA enforce 4-eyes principe; Sensitive Vault bucket met striktere encryption |
| **AVG art. 22 (geen volledig automatisch besluit)** | Mens-in-de-lus enforced via workflow; modellen scoren, behandelaar beslist |
| **AVG inzage/correctie/verwijdering** | dbt models met `bsn` als unique key; dedicated `gdpr_request` DAG die per BSN raadpleegt en/of verwijdert |
| **BIO encryption at rest** | MinIO server-side encryption + Stackable secret-operator + cert-manager TLS |
| **BIO encryption in transit** | Stackable AuthenticationClass TLS, alle interne traffic mTLS |
| **BIO MFA** | Keycloak met TOTP/WebAuthn; AuthenticationClass OIDC |
| **BIO logging 6+ maanden** | Vector → OpenSearch (lange retentie); Trino event listener naar Kafka → S3 immutable |
| **NIS2 incident detection** | Prometheus alerts + OPA decision logging in OpenSearch + SIEM-integratie |
| **NIS2 vulnerability mgmt** | Stackable images SBOM (verifieerbaar via cosign); CIS K8s Benchmarks |
| **AI Act hoog-risico** | OM `risk_tier` classifications + verplichte model card als markdown in dbt-docs |
| **NORA open standaarden** | Iceberg, Parquet, OpenLineage, OIDC, REST — geen proprietary formaten |

---

Zie verder het bestand `MASTER-AGENT-PROMPT.md` voor de volledige instructie aan Claude Code.
