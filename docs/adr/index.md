---
title: Decisions (ADRs) — overzicht
description: Architecture Decision Records die de fundamentele keuzes vastleggen.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Changes handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Architecture Decision Records (ADRs)

Numbered, immutable. Een nieuwe beslissing krijgt een nieuw ADR; de oude
wordt niet bewerkt maar als "superseded by" gemarkeerd.

| ADR | Beslissing | Status |
|---|---|---|
| [0001](0001-stackable-as-base.md) | Stackable Data Platform als basis | Accepted |
| [0002](0002-iceberg-vs-delta.md) | Iceberg vs Delta — afweging | Superseded by 0006 |
| [0003](0003-opa-as-trino-authz.md) | OPA als Trino-autorisatie-engine | Accepted |
| [0004](0004-openmetadata-as-catalog.md) | OpenMetadata als catalog/lineage/DQ | Accepted |
| [0005](0005-dbt-trino-as-transform.md) | dbt-trino als transformationlaag | Accepted |
| [0006](0006-delta-chosen-for-this-implementation.md) | Delta gekozen voor deze implementatie | Accepted |
| [0007](0007-airflow-pipeline-architecture.md) | Airflow pipeline-architecture | Accepted |
| [0008](0008-self-service-data-access.md) | Self-service data-access flow | Accepted |

## ADR-format

Elke ADR volgt dezelfde indeling:

- **Status** — Proposed / Accepted / Deprecated / Superseded by N
- **Context** — wat speelt er, welke krachten werken on the keuze
- **Beslissing** — wat is besloten
- **Gevolgen** — wat verandert er door deze keuze
- **Alternatieven** — wat is overwogen en waarom afgewezen
