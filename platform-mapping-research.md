# Platform Mapping Research

Survey of the open-source landscape that the ODAP reference platform draws
on, and how each chosen tool maps onto the architectural layers in
[`reference-architecture.md`](reference-architecture.md).

## Layer × tool matrix

| Layer | Chosen tool | Why | Considered alternatives |
|---|---|---|---|
| **Identity** | Keycloak | Mature OIDC + SAML; rich admin API; Stackable does not ship its own IdP. | Authelia (lighter, fewer features), Dex (less polished admin). |
| **Object storage** | MinIO | S3-compatible, single binary, runs anywhere; production-grade with HA. | Ceph RGW (heavier), Garage (less mature), AWS S3 direct (vendor lock-in). |
| **Table format** | Delta Lake (default), Iceberg behind abstraction | Best Trino + Spark interop in late 2025; mature `MERGE` + time travel. | Iceberg (chosen as default in many vendor stacks; we keep it path-supported). Hudi (less momentum). |
| **Metastore** | Hive Metastore (Postgres-backed) | Lingua franca; both Trino and Spark consume it. | Unity Catalog (Databricks-tied), Polaris (early stage), Iceberg REST catalog. |
| **Query engine** | Trino | Federated SQL, mature OPA integration, dbt support. | Presto (parent fork, less velocity), Dremio, Spark SQL alone. |
| **Transformation** | dbt-trino | SQL-first, test-first, lineage included; cosmos integrates it with Airflow. | SQLMesh (newer, less mature), Spark SQL pipelines (less idiomatic). |
| **Orchestration** | Airflow 3 + astronomer-cosmos | Standard scheduler; cosmos turns dbt projects into native DAGs. | Dagster, Prefect, Argo Workflows. |
| **BI** | Superset + Power BI | Superset for everyone (no vendor cost); Power BI for analysts with Excel/DAX fluency. | Metabase, Looker, Grafana for BI. |
| **Notebooks** | JupyterHub + KubeSpawner | Native K8s; per-user pods; ODAP Lab kernel includes `odap_lab` helpers. | Coder, Zeppelin, hosted Databricks/Sagemaker (vendor lock-in). |
| **Policy** | OPA (Rego) | Best-in-class for fine-grained authorization; Trino + Kafka + Kubernetes all integrate natively. | Cedar (newer), Casbin (less mature). |
| **Catalog / lineage / DQ** | OpenMetadata | Single tool that combines catalog + lineage + glossary + DQ; very active community. | DataHub, Amundsen, Atlan/Collibra (vendor). |
| **Metrics** | Prometheus | De facto K8s standard. | VictoriaMetrics. |
| **Logs** | Vector → OpenSearch | Vector ships fast, OpenSearch single-node is cheap. | Loki + Grafana, ELK, Datadog. |
| **Tracing** | OpenTelemetry collectors wired (backend TBD) | OTLP receivers in Trino + Airflow already configured. | Jaeger, Tempo. |
| **Kubernetes ops** | Stackable Data Platform operators | Curated CRDs for the Apache stack (Hive, Spark, Trino, Airflow, Kafka, NiFi, ZooKeeper, OPA, Superset). | Bespoke Helm charts per tool; cloud-managed equivalents (vendor-specific). |
| **AI / agents** | Multica + Nanitics (exploratory) | Demonstrates an agent loop coupled to platform telemetry. | OpenDevin, Cursor in-IDE (different model — outside cluster). |

## Stack-level positioning

ODAP **assembles** open-source projects; it does **not** reinvent them. The
value-add of this reference is:

1. **A coherent default for the layer wiring** — what talks to what, with
   what protocol, with what credential.
2. **Policy as code, governed by default** — OPA bundles auto-generated from
   role-mapping JSON; no policy lives in application code.
3. **Single-shell UX** — the portal embeds every service UI so end users see
   one URL.
4. **Mode-portable manifests** — same `platform/` directory deploys to k3d
   (laptop) and managed K8s in two clouds with overlays only.
5. **Compliance traceability** — every architectural decision links forward
   to GDPR / ISO 27001 / NIS2 / AI Act / SOC 2 controls.

## What's deliberately not in scope

- **CDC**: source-system change capture (Debezium, Fivetran, Airbyte) is out
  of scope; the reference assumes event-stream producers or batch landings.
- **Feature store**: not chosen; if needed, Feast slots in next to Trino.
- **Vector search**: out of scope; OpenSearch's built-in vector engine
  exists but isn't exercised here.
- **Stream processing beyond Spark Structured Streaming**: no Flink in this
  release; the architecture allows it via the Stackable Flink operator if
  the use case demands.
