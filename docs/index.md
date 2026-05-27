---
title: Home
description: ODAP reference implementation van een compliant data- en analyticsplatform.
hide:
  - navigation
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Changes handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Open Data & Analytics Platform

Een **fictieve, illustratieve** reference implementation van een modern data-
en analyticsplatform voor UWV, gebouwd op open source en gericht op compliance
met GDPR, ISO 27001/27002, NIS2, and the EU AI Act.

!!! warning "Geen echte ODAP data"
    Geen echte BSN's, geen echte productioncode. Alle datasets zijn synthetisch
    en gemarkeerd met `# SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE`.
    Deze repo is geen ODAP product en geen aanbestedingsstuk.

## Wat vind je hier?

<div class="grid cards" markdown>

-   :material-sitemap:{ .lg .middle } **Architecture**

    ---

    19 components over 9 lagen — van ingestion
    tot consumptie, met identity, observability en governance als
    cross-cutting lanen.

    [:octicons-arrow-right-24: Open architecture](architecture/index.md)

-   :material-account-group:{ .lg .middle } **Voor wie?**

    ---

    12 rollen met elk eigen handbook: Claims Analyst,
    Fraud Analyst, data-engineer, platform-admin, … Access en data-zichtbaarheid
    komen uit OPA-policies en Keycloak-rollen.

    [:octicons-arrow-right-24: Bekijk rollen](rollen/index.md)

-   :material-target:{ .lg .middle } **Use cases**

    ---

    11 concrete business-flows — van WIA-funnel (UC-01) tot
    integrale customer journey (UC-11) — met scope, CGM-entiteiten, purpose-limitation
    en AI-Act-classificatie.

    [:octicons-arrow-right-24: Bekijk use cases](use-cases/index.md)

-   :material-clipboard-text:{ .lg .middle } **Decisions**

    ---

    8 ADRs leggen de fundamentele keuzes vast: Stackable, Delta vs Iceberg,
    OPA als Trino-authz, OpenMetadata als catalog, dbt-trino als
    transformationlaag.

    [:octicons-arrow-right-24: Bekijk ADRs](adr/index.md)

-   :material-shield-check:{ .lg .middle } **Compliance**

    ---

    Iedere R-GDPR/ISO27001/NIS2/NIS2/AI-Act-requirement is gemapt op een concreet
    bestand of setting — herleidbaar in code en config.

    [:octicons-arrow-right-24: Compliance-mapping](compliance-mapping.md)

-   :material-cog:{ .lg .middle } **Operations**

    ---

    Runbook, security-policy, documentation-gaps, roadmap. De operationele
    realiteit van het platform.

    [:octicons-arrow-right-24: Operations](runbook.md)

</div>

## Quick start

```bash
# Prerequisites: Docker Desktop (≥ 8 GB / ≥ 4 CPU), k3d ≥ 5.6, kubectl, helm, stackablectl

git clone https://github.com/fresh-minds/FreshStackableDataPlatform.git
cd FreshStackableDataPlatform

# DNS-injectie voor lokale access
echo "127.0.0.1 keycloak.odap.local \
  superset.odap.local airflow.odap.local \
  minio.odap.local openmetadata.odap.local" | sudo tee -a /etc/hosts

# Cluster + platform deployen (~15-30 min on the eerste run)
make cluster        # k3d cluster create
make bootstrap      # cert-manager, MinIO, Postgres, Keycloak, Stackable operators
make deploy-platform # Trino, Spark, Kafka, NiFi, Airflow, Superset, OpenMetadata
make seed           # synthetische data laden (10k cliënten)
make test           # smoke tests
```

## Wat is de stack?

| Laag | Component | Kort |
|---|---|---|
| Identity | **Keycloak** | OIDC, MFA, rol-claims |
| Ingestion | **NiFi → Kafka** | Visuele flows, schaalbare event-bus |
| Storage | **MinIO + Hive Metastore** | S3-compatible, Delta-tabellen, catalog |
| Processing | **Spark (Stackable)** | Structured Streaming + batch |
| Query | **Trino + OPA** | SQL over lakehouse met policy-checks |
| Transformation | **dbt-trino** | Staging → intermediate → marts, format-agnostisch |
| Orkestratie | **Airflow** | DAGs voor batch + dbt-runs |
| BI | **Superset** | Dashboards + SQL Lab |
| Governance | **OpenMetadata** | Catalog, glossary, lineage, DQ |
| Observability | **Vector → OpenSearch + Prometheus + OTEL** | Logs, metrics, traces |

Alle components via **Stackable Data Platform 26.3** operators.

## Bijdragen

Issues, PR's en feedback welcome via [GitHub](https://github.com/fresh-minds/FreshStackableDataPlatform).
Een nieuwe doc volgt de bestaande structuur (ADR ↔ use-case ↔ handbook);
kruisverwijzingen worden bijgewerkt in dit document én in de index.
