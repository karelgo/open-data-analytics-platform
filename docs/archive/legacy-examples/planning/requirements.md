# Requirements — Compliant Data & Analytics Platform

Functional and non-functional requirements that the platform aims to
demonstrate. Numbering is preserved across compliance frameworks for
traceability with `docs/compliance-mapping.md`.

---

## R-GDPR — General Data Protection Regulation (EU 2016/679)

| ID | Requirement |
|---|---|
| R-GDPR-01 | Personal data is classified at ingestion: `none` / `pseudonymous` / `direct PII` / `special-category` (medical, biometric, etc.). |
| R-GDPR-02 | Purpose limitation is enforced at query time. Each query carries a declared `purpose`; OPA verifies it against the dataset's allow-list. |
| R-GDPR-03 | Data subjects can be looked up by stable `customer_id`; right-to-be-forgotten propagates from `customers.deleted` events through Delta `DELETE` on all downstream tables. |
| R-GDPR-04 | Data access logs are retained for 7 years (audit retention class). |
| R-GDPR-05 | Cross-border transfers default to EU-only (storage class + cluster region pinned to EU). |
| R-GDPR-06 | Data Processing Records (Art. 30) auto-generated from OpenMetadata classifications + role-mapping + retention class. |
| R-GDPR-07 | Pseudonymisation key (salt) is managed in a Kubernetes Secret, rotated quarterly, with audit trail in OpenSearch. |

## R-ISO27K — ISO 27001 / 27002

| ID | Requirement |
|---|---|
| R-ISO-01 | Asset inventory maintained in OpenMetadata; every Delta table, dbt model, Trino catalog, and component has an owner. |
| R-ISO-02 | Access control via Keycloak realm roles + OPA; no shared credentials. |
| R-ISO-03 | Cryptography in transit: TLS 1.2+ on every ingress; in-cluster TLS via Stackable SecretClass. |
| R-ISO-04 | Cryptography at rest: MinIO server-side encryption, Postgres at-rest via the cloud provider's encrypted volumes. |
| R-ISO-05 | Change management: every platform change goes through Git + PR review; `platform-config.yaml` is the single source for tunables. |
| R-ISO-06 | Audit logging: OPA decision logs, Keycloak audit events, MinIO access logs, dbt run history — all shipped to OpenSearch by Vector. |
| R-ISO-07 | Vulnerability management: container images pinned by digest; Renovate / Dependabot watches for updates. |

## R-NIS2 — Network and Information Security Directive 2

| ID | Requirement |
|---|---|
| R-NIS2-01 | Incident detection via Prometheus alert rules + Alertmanager → email/Slack/PagerDuty. |
| R-NIS2-02 | NetworkPolicies enforce default-deny at the namespace boundary; ingress and egress are explicitly allow-listed per workload (see ADR-0009). |
| R-NIS2-03 | Supply-chain hygiene: Stackable release pinned by version + digest; Helm releases pinned; image provenance documented in `infrastructure/stackablectl/release.yaml`. |
| R-NIS2-04 | Backup & restore: Postgres dumps via CronJob to MinIO; restore drill documented in `docs/runbook.md`. |
| R-NIS2-05 | Multi-factor authentication for `platform_admin` enforced at Keycloak. |
| R-NIS2-06 | Incident response runbook (`docs/runbook.md`) covers triage, escalation, and post-mortem. |

## R-AIACT — EU AI Act (EU 2024/1689)

| ID | Requirement |
|---|---|
| R-AIACT-01 | Algorithm registry: every ML model artefact carries `algorithm_id` metadata in OpenMetadata. |
| R-AIACT-02 | Risk classification: each model tagged `minimal_risk` / `limited_risk` / `high_risk` / `unacceptable`. |
| R-AIACT-03 | Human-in-the-loop checkpoints documented per high-risk model in `docs/use-cases/uc<NN>-*.md`. |
| R-AIACT-04 | Training-data lineage captured from bronze through silver to the model artefact via dbt + OpenMetadata. |
| R-AIACT-05 | Model performance monitored via Prometheus + Grafana; drift alerts go to the model owner. |
| R-AIACT-06 | Sandbox zone (separate Trino catalog) for experimentation; no production data flows back without review. |

## R-SOC2 — SOC 2 Trust Services Criteria

| ID | Requirement |
|---|---|
| R-SOC2-01 | **Security**: OPA policy unit tests gate every change to `opa-policies-src/`. |
| R-SOC2-02 | **Availability**: SLO targets per service tracked in Prometheus (Trino coordinator uptime ≥ 99.5%, OpenMetadata ≥ 99%). |
| R-SOC2-03 | **Confidentiality**: PII columns hashed/masked unless role + purpose explicitly grants clear text. |
| R-SOC2-04 | **Processing integrity**: dbt tests run on every build; failed tests block downstream marts. |
| R-SOC2-05 | **Privacy**: same as R-GDPR-*. |

## R-PLAT — Platform-engineering requirements

| ID | Requirement |
|---|---|
| R-PLAT-01 | Single command brings up the full platform (`make deploy MODE=k3d`). |
| R-PLAT-02 | Same manifests deploy to k3d (local), AKS (Azure), and SKE (StackIT), differentiated only by kustomize overlays + Helm value files. |
| R-PLAT-03 | All tunables live in `platform-config.yaml`; component manifests reference it via Helm values (no duplicated config). |
| R-PLAT-04 | New table-format support (e.g. Iceberg) added by toggling `table_format: iceberg` in `platform-config.yaml`; dbt macros adapt automatically. |
| R-PLAT-05 | OPA policies tested in CI (`opa test`); regressions block merges. |
| R-PLAT-06 | Documentation site (`mkdocs serve`) builds without warnings on every push. |

## R-DATA — Data-quality requirements

| ID | Requirement |
|---|---|
| R-DATA-01 | Every silver table has at least one `not_null`, one `unique` or `surrogate_key`, and one relationship test. |
| R-DATA-02 | DQ violations open a dashboard tile (`mart_uc_dq_overview`) plus a Slack notification to the dataset owner. |
| R-DATA-03 | Pseudonymisation drift (different salts producing different hashes for the same input) detected by a daily smoke test. |
| R-DATA-04 | Schema-evolution events (column added / removed / type change) recorded in OpenMetadata as version events. |

---

For control-by-control compliance mapping (which control maps to which
platform feature), see [`docs/compliance-mapping.md`](docs/compliance-mapping.md).
