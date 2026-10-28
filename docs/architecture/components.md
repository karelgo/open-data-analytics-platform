# Platform components

The active data journey is [Dutch IT Job Market](../use-cases/dutch-it-job-market.md). Optional infrastructure is listed here for reference; it is not required by that batch pipeline.

| Component | Role | Stage |
|---|---|---|
| Keycloak | OIDC identity provider — single sign-on and MFA for every component. | identity |
| Apache NiFi | Visual ingestion flows — source systems → Kafka. | ingestion |
| Kafka | Event bus between NiFi ingestion and Spark Structured Streaming. | ingestion |
| MinIO | S3-compatible object store with buckets bronze/silver/gold/sensitive. | storage |
| Hive Metastore | Catalog backend — tracks table schemas and partitions for Trino and Spark. | storage |
| Apache Spark | Streaming + batch jobs that write Delta tables on MinIO. | transformation |
| Trino | SQL query engine over the Delta lakehouse, with OPA authorization. | transformation |
| OPA | Open Policy Agent — decides per Trino query what a role may see (row filters, column masks, purpose limitation). | transformation |
| Apache Superset | Dashboards and SQL Lab — primary UI for most end users. | consumption |
| OpenMetadata | Catalog, glossary, lineage, data quality. | discovery |
| dbt docs | Models, tests, sources, and lineage from the dbt project definitions. | discovery |
| ODAP Lab (Jupyter) | Notebook environment — Python/SQL on bronze/silver/gold/sensitive, with Git integration. | consumption |
| Apache Airflow | DAG orchestration for batch jobs and dbt runs. | pipeline |
| Prometheus | Metrics + alerts; feeds the status badges in this portal. | observability |
| Grafana | Dashboards on Prometheus metrics — cluster health and service latency. | observability |
| OpenSearch | Logs (Vector) + search backend for OpenMetadata. | observability |
| Multica | Coordination of coding agents (Claude Code, Codex, Copilot CLI, …) — tasks, progress, skills. | agents |
| Power BI | Dashboards and self-service exploration via Microsoft Fabric / Power BI (own Azure-tenant SSO). | consumption |
| Nanitics Observatory | In-cluster agent runtime + trace viewer. Watcher monitors the platform and files issues to Multica. | agents |
