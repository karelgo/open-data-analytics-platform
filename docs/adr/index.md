# Architecture decisions

Decisions record the platform's history. Earlier domain examples mentioned in these records are historical; the active use case is [Dutch IT Job Market](../use-cases/dutch-it-job-market.md).

- [ADR-0001: Stackable Data Platform als operator-baseline](0001-stackable-as-base.md)
- [ADR-0002: Iceberg of Delta Lake als tabelformaat](0002-iceberg-vs-delta.md)
- [ADR-0003: Open Policy Agent als authorisatielaag voor Trino](0003-opa-as-trino-authz.md)
- [ADR-0004: OpenMetadata als catalog, governance en lineage-laag](0004-openmetadata-as-catalog.md)
- [ADR-0005: dbt-core + dbt-trino als transformationlaag](0005-dbt-trino-as-transform.md)
- [ADR-0006: Delta Lake gekozen voor déze reference implementation](0006-delta-chosen-for-this-implementation.md)
- [ADR-0007: Airflow pipeline-architecture — Cosmos, Datasets, YAML-registry](0007-airflow-pipeline-architecture.md)
- [ADR-0008: Microsoft Entra ID via Keycloak-brokering (i.p.v. parallelle IDPs)](0008-entra-broker-via-keycloak.md)
- [ADR-0008: Self-service data access via OpenMetadata + OPA-brug](0008-self-service-data-access.md)
- [ADR-0009: NetworkPolicies — default-deny in cloud, off in k3d](0009-networkpolicies-strategy.md)
- [ADR-0010: platform-config.yaml als single source of truth](0010-platform-config-single-source.md)
