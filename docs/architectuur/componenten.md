---
title: Componenten
description: Per-component overzicht — verantwoordelijkheid, doel, URL, gebruikende rollen.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Wijzigingen handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Componenten

Per-component overzicht. Voor het diagram op laag-niveau zie
[Architectuur · Overzicht](index.md); voor de relatie tussen rollen en
componenten zie de [rol-matrix](#rol-matrix) onderaan.

## Identiteit & Toegang

_SSO regelt wie wat mag — elk onderdeel checkt het token._

### Keycloak { #keycloak }

!!! abstract "Wat doet Keycloak?"
    Eén keer inloggen, overal toegang volgens je rol. MFA en audit-log centraal.

**Laag:** `auth` · **Stage:** `identity` · **Prometheus job:** `keycloak`

OIDC-identity provider — single sign-on en MFA voor alle componenten.

- **URL:** [Live UI ↗](https://keycloak.odap.local:8443)
- **Gebruikt door:** **alle rollen**

## Ingestie

_Data binnenhalen en op een event-bus zetten._

### Apache NiFi { #nifi }

!!! abstract "Wat doet Apache NiFi?"
    Data uit UWV-bronsystemen ophalen en in het platform binnenbrengen.

**Laag:** `streaming` · **Stage:** `ingestion` · **Prometheus job:** `nifi`

Visuele ingestion-flows — bronsystemen → Kafka.

- **URL:** _geen UI_
- **Gebruikt door:** `platform_admin`, `data_engineer`

### Kafka { #kafka }

!!! abstract "Wat doet Kafka?"
    Data-events bufferen en doorzetten naar verwerking. Schaalbare doorvoer.

**Laag:** `streaming` · **Stage:** `ingestion` · **Prometheus job:** `kafka`

Event-bus tussen NiFi-ingestion en Spark Structured Streaming.

- **URL:** _geen UI_
- **Gebruikt door:** `platform_admin`, `data_engineer`

## Opslag & Verwerking

_Lakehouse met zones en een tabel-catalog._

### MinIO { #minio }

!!! abstract "Wat doet MinIO?"
    Het lakehouse waar alle data fysiek staat — gelaagd in zones met aparte toegangsregels.

**Laag:** `storage` · **Stage:** `storage` · **Prometheus job:** `minio`

S3-compatible object store met buckets bronze/silver/gold/sensitive.

- **URL:** `/go/minio/`
- **Gebruikt door:** `platform_admin`, `data_engineer`

### Hive Metastore { #hive }

!!! abstract "Wat doet Hive Metastore?"
    Vertaalt bestanden in MinIO naar tabellen met kolommen en types.

**Laag:** `metadata` · **Stage:** `storage` · **Prometheus job:** `hive`

Catalog backend — houdt tabel-schemas en partities bij voor Trino en Spark.

- **URL:** _geen UI_
- **Gebruikt door:** `platform_admin`, `data_engineer`

## Transformatie & Modellen

_Opschonen, joinen, modelleren — met policy-checks per query._

### Apache Spark { #spark }

!!! abstract "Wat doet Apache Spark?"
    Zware data-bewerkingen — opschonen, joinen, aggregeren — in stream of batch.

**Laag:** `compute` · **Stage:** `transformation` · **Prometheus job:** `spark`

Streaming + batch jobs die Delta-tabellen op MinIO schrijven.

- **URL:** [Live UI ↗](https://spark.odap.local:8443)
- **Gebruikt door:** `platform_admin`, `data_engineer`

### Trino { #trino }

!!! abstract "Wat doet Trino?"
    Snel SQL draaien over de hele lakehouse — voor dbt-modellen én eindgebruikers.

**Laag:** `query` · **Stage:** `transformation` · **Prometheus job:** `trino`

SQL query-engine over Delta-lakehouse, met OPA-authorisatie.

- **URL:** _geen UI_
- **Gebruikt door:** `wia_beoordelaar`, `ww_handhaver`, `wajong_arbeidsdeskundige`, `fez_analist`, `smz_planner`, `proactief_dienstverlener`, `researcher`, `data_steward`, `data_engineer`, `platform_admin`

### OPA { #opa }

!!! abstract "Wat doet OPA?"
    Doelbinding, rij-filters en kolom-maskering afdwingen op iedere query.

**Laag:** `policy` · **Stage:** `transformation` · **Prometheus job:** `opa`

Open Policy Agent — beslist per Trino-query wat een rol mag zien (rij-filters, kolom-maskers, doelbinding).

- **URL:** _geen UI_
- **Gebruikt door:** `platform_admin`

## BI / Analytics

_Eindgebruikers consumeren via dashboards en SQL._

### Apache Superset { #superset }

!!! abstract "Wat doet Apache Superset?"
    Dashboards en ad-hoc analyse voor business-rollen — zonder SQL hoeven kennen.

**Laag:** `bi` · **Stage:** `consumption` · **Prometheus job:** `superset`

Dashboards en SQL Lab — primaire UI voor de meeste eindgebruikers.

- **URL:** [Live UI ↗](https://superset.odap.local:8443)
- **Gebruikt door:** `wia_beoordelaar`, `ww_handhaver`, `wajong_arbeidsdeskundige`, `crm_medewerker`, `fez_analist`, `smz_planner`, `proactief_dienstverlener`, `researcher`, `data_steward`, `platform_admin`

### ODAP Lab (Jupyter) { #jupyter }

!!! abstract "Wat doet ODAP Lab (Jupyter)?"
    Interactief data verkennen en analyseren — Trino, Delta, MinIO, OpenMetadata vanuit één Python-kernel; werk versioneren met Git.

**Laag:** `compute` · **Stage:** `consumption` · **Prometheus job:** _niet gemonitord_

Notebook-werkomgeving — Python/SQL op bronze/silver/gold/sensitive, met Git-integratie.

- **URL:** [Live UI ↗](https://jupyter.odap.local:8443)
- **Gebruikt door:** `researcher`, `data_engineer`, `data_steward`, `wajong_arbeidsdeskundige`, `fez_analist`, `platform_admin`

### Power BI { #powerbi }

!!! abstract "Wat doet Power BI?"
    Curated dashboards bovenop het lakehouse + composite-model self-service voor analisten met DAX/Excel-skills.

**Laag:** `bi` · **Stage:** `consumption` · **Prometheus job:** _niet gemonitord_

Dashboards en self-service exploration via Microsoft Fabric / Power BI (eigen Azure-tenant SSO).

- **URL:** [Live UI ↗](https://app.fabric.microsoft.com)
- **Gebruikt door:** `wia_beoordelaar`, `ww_handhaver`, `wajong_arbeidsdeskundige`, `crm_medewerker`, `fez_analist`, `smz_planner`, `proactief_dienstverlener`, `researcher`, `data_analyst`, `data_steward`, `platform_admin`

## Data Discovery

_Catalog, lineage en data-kwaliteit — wat hebben we eigenlijk?_

### OpenMetadata { #openmetadata }

!!! abstract "Wat doet OpenMetadata?"
    Wat hebben we, wie is eigenaar, hoe is het opgebouwd, en is het op orde?

**Laag:** `governance` · **Stage:** `discovery` · **Prometheus job:** `openmetadata`

Catalog, glossary, lineage, data-quality.

- **URL:** [Live UI ↗](https://openmetadata.odap.local:8443)
- **Gebruikt door:** `wia_beoordelaar`, `ww_handhaver`, `wajong_arbeidsdeskundige`, `crm_medewerker`, `fez_analist`, `smz_planner`, `researcher`, `data_steward`, `data_engineer`, `platform_admin`

### dbt docs { #dbt-docs }

!!! abstract "Wat doet dbt docs?"
    Wat doen onze dbt-modellen, welke tests draaien er, en hoe vloeit data van staging naar marts?

**Laag:** `governance` · **Stage:** `discovery` · **Prometheus job:** _niet gemonitord_

Modellen, tests, sources en lineage van de dbt-projectdefinities.

- **URL:** `/dbt-docs.html`
- **Gebruikt door:** `data_engineer`, `data_steward`, `platform_admin`

## Pipeline-orkestratie

_Wat draait wanneer, in welke volgorde, met welke afhankelijkheid._

### Apache Airflow { #airflow }

!!! abstract "Wat doet Apache Airflow?"
    Plant en bewaakt alle scheduled jobs — wat draait wanneer, in welke volgorde.

**Laag:** `orchestration` · **Stage:** `pipeline` · **Prometheus job:** `airflow`

DAG-orchestratie voor batch-jobs en dbt-runs.

- **URL:** [Live UI ↗](https://airflow.odap.local:8443)
- **Gebruikt door:** `platform_admin`, `data_engineer`

## Observability

_Metrics, logs en alerts om de gezondheid van het platform te zien._

### Prometheus { #prometheus }

!!! abstract "Wat doet Prometheus?"
    Metrics verzamelen en alerteren als iets stuk dreigt te gaan.

**Laag:** `observability` · **Stage:** `observability` · **Prometheus job:** `prometheus-kube-prometheus-prometheus`

Metrics + alerts; voedt de status-badges in deze portal.

- **URL:** [Live UI ↗](https://prometheus.odap.local:8443)
- **Gebruikt door:** `platform_admin`

### Grafana { #grafana }

!!! abstract "Wat doet Grafana?"
    Visualisatie van Prometheus-metrics in dashboards; gateway voor SRE-werk.

**Laag:** `observability` · **Stage:** `observability` · **Prometheus job:** `prometheus-grafana`

Dashboards over Prometheus-metrics — cluster-health en service-latency.

- **URL:** [Live UI ↗](https://grafana.odap.local:8443)
- **Gebruikt door:** `platform_admin`, `data_engineer`

### OpenSearch { #opensearch }

!!! abstract "Wat doet OpenSearch?"
    Logs centraal doorzoekbaar maken — debugging en audit-trail.

**Laag:** `observability` · **Stage:** `observability` · **Prometheus job:** `opensearch`

Logs (Vector) + search-backend voor OpenMetadata.

- **URL:** [Live UI ↗](https://opensearch.odap.local:8443)
- **Gebruikt door:** `platform_admin`, `data_steward`

## Agents & AI-tooling

_Coördinatie van coding agents (Multica) en gerelateerde dev-loop tooling._

### Multica { #multica }

!!! abstract "Wat doet Multica?"
    Taken toewijzen aan coding agents; voortgang volgen. Agents draaien op je laptop.

**Laag:** `ai-agents` · **Stage:** `agents` · **Prometheus job:** `multica-backend`

Coördinatie van coding agents (Claude Code, Codex, Copilot CLI, …) — taken, voortgang, skills.

- **URL:** [Live UI ↗](https://multica.odap.local:8443)
- **Gebruikt door:** `platform_admin`, `data_engineer`

### Nanitics Observatory { #nanitics }

!!! abstract "Wat doet Nanitics Observatory?"
    Bekijk watcher-runs (span tree, LLM-calls, tool-calls) en triggert handmatige investigations.

**Laag:** `ai-agents` · **Stage:** `agents` · **Prometheus job:** _niet gemonitord_

In-cluster agent-runtime + trace-viewer. Watcher monitort het platform en filed issues naar Multica.

- **URL:** [Live UI ↗](https://nanitics.odap.local:8443/api/observatory/)
- **Gebruikt door:** `platform_admin`, `data_engineer`


## Rol-matrix { #rol-matrix }

Welke rol gebruikt welk component? Een ✓ betekent dat de rol in deze
referentie-implementatie via de portal-shortcuts naar de UI van het
component wordt gestuurd. Een lege cel betekent dat de rol normaliter geen
directe toegang nodig heeft (toegang kan alsnog via JIT/break-glass).

| Rol | keycloak | nifi | kafka | minio | hive | spark | trino | opa | superset | openmetadata | dbt-docs | jupyter | airflow | prometheus | grafana | opensearch | multica | powerbi | nanitics |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `wia_beoordelaar` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `ww_handhaver` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `wajong_arbeidsdeskundige` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `crm_medewerker` | ✓ |  |  |  |  |  |  |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `fez_analist` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `smz_planner` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  | ✓ |  |
| `proactief_dienstverlener` | ✓ |  |  |  |  |  | ✓ |  | ✓ |  |  |  |  |  |  |  |  | ✓ |  |
| `researcher` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ |  | ✓ |  |  |  |  |  | ✓ |  |
| `data_steward` | ✓ |  |  |  |  |  | ✓ |  | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |  | ✓ |  |
| `data_engineer` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ | ✓ | ✓ | ✓ |  | ✓ |  | ✓ |  | ✓ |
| `platform_admin` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `data_analyst` | ✓ |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | ✓ |  |
