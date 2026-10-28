# Reference Architecture — Open Data & Analytics Platform (ODAP)

A reference implementation of a modern, compliant data & analytics platform.
Vendor-neutral, open-source-first, designed for regulated industries (financial
services, insurance, healthcare, public sector).

This document describes the **what** and **why** behind the architecture.
For the **how** (manifests, Helm values, deployment), see `platform/`,
`infrastructure/`, and `docs/runbook.md`.

---

## 1. Goals

The platform must:

1. **Compose, not lock-in.** Every layer (storage, table format, query engine,
   transformation, BI, orchestration, catalog, identity) is replaceable.
2. **Govern by default.** Policy lives next to data, not in the application;
   row filters, column masks, and purpose limitation are enforced at query
   time.
3. **Make data discoverable.** Every dataset has an owner, classification,
   lineage, and a documented purpose before it lands in a dashboard.
4. **Run on Kubernetes.** Both local (k3d) and managed cloud (AKS, StackIT
   SKE) — the same manifests, with overlays for storage class, ingress, and
   DNS.
5. **Demonstrate compliance**: GDPR, ISO 27001 / 27002, NIS2, the EU AI Act,
   plus SOC 2-aligned operational controls.

---

## 2. Architecture overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ODAP Portal (Astro/React)                  │
│         single shell, role-aware launchpad, embedded UIs            │
├─────────────────────────────────────────────────────────────────────┤
│  Sources          Ingestion       Storage          Transformation   │
│  ┌─────────┐      ┌────────┐      ┌────────┐       ┌──────────────┐ │
│  │Synthetic│ →    │ NiFi   │ →    │ MinIO  │ ←     │  Spark       │ │
│  │generators│     │ Kafka  │      │ Delta  │  ←    │  dbt-trino   │ │
│  └─────────┘      └────────┘      └────────┘       └──────────────┘ │
│         │                              │                    │       │
│         ↓                              ↓                    ↓       │
│   Hive Metastore       OpenMetadata Catalog          Trino SQL      │
│   (schemas / partitions)  (lineage + DQ)             (OPA-authzed)  │
│                                                                     │
│  Consumption                          Cross-cutting                 │
│  ┌──────────┐  ┌─────────┐            ┌────────────┐                │
│  │ Superset │  │ Jupyter │            │ Keycloak   │ (OIDC SSO)     │
│  │ Power BI │  │ ODAP Lab│            │ OPA        │ (authz)        │
│  └──────────┘  └─────────┘            │ Prometheus │ (metrics)      │
│                                       │ Grafana    │ (dashboards)   │
│                                       │ OpenSearch │ (logs)         │
│                                       │ Vector     │ (log shipping) │
│                                       └────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 Lakehouse zones

| Zone | Catalog | Purpose | Retention |
|---|---|---|---|
| **bronze** | `bronze` | Raw event-stream landings, append-only | 7 days minimum |
| **silver** | `silver` | Conformed, typed, deduplicated | 2 years |
| **gold** | `gold` | Modelled marts per use case | 5 years (use-case dependent) |
| **sensitive** | `sensitive` | Restricted; four-eyes required | per data type |
| **sandbox** | `sandbox` | Researcher area on pseudonymised inputs | 90 days |

Zone separation is enforced by:
- MinIO bucket-level policies (per zone).
- Trino catalogs (one per zone, with separate OPA package roots).
- OPA rules (`opa-policies-src/trino/*.rego`) that gate per-role access.

### 2.2 Medallion + data-mesh hybrid

The medallion pattern (bronze/silver/gold) gives a clean technical layering.
On top of it, the dbt staging tree is organised by **business domain**
(`customers`, `claims`, `service_requests`, `eligibility_cases`, `incidents`,
`finance`, `policies`, `persons`, `customer_satisfaction`). Each domain owns
its silver tables and exposes them to the gold use-case marts via the dbt
DAG. This gives the data-mesh property "each domain owns its data" without
the operational overhead of separate compute clusters per domain.

---

## 3. Component decisions (ADR pointers)

| Decision | ADR |
|---|---|
| Stackable as the operator base | [ADR-0001](docs/adr/0001-stackable-as-base.md) |
| Open table format: Iceberg vs. Delta | [ADR-0002](docs/adr/0002-iceberg-vs-delta.md) |
| OPA as Trino authorization layer | [ADR-0003](docs/adr/0003-opa-as-trino-authz.md) |
| OpenMetadata as catalog | [ADR-0004](docs/adr/0004-openmetadata-as-catalog.md) |
| dbt-trino as transformation layer | [ADR-0005](docs/adr/0005-dbt-trino-as-transform.md) |
| Delta Lake chosen for this impl. | [ADR-0006](docs/adr/0006-delta-chosen-for-this-implementation.md) |
| Airflow pipeline architecture | [ADR-0007](docs/adr/0007-airflow-pipeline-architecture.md) |
| Self-service data access workflow | [ADR-0008](docs/adr/0008-self-service-data-access.md) |
| NetworkPolicies strategy | [ADR-0009](docs/adr/0009-networkpolicies-strategy.md) |
| `platform-config.yaml` as single source | [ADR-0010](docs/adr/0010-platform-config-single-source.md) |

---

## 4. Identity, authorization, and policy

### 4.1 Authentication

Keycloak is the OIDC identity provider. All component-level access is mediated
through Keycloak:

- **Trino**, **Superset**, **Airflow**, **NiFi**, **OpenMetadata**, **Jupyter**:
  OIDC clients in the `odap` realm.
- **MinIO Console**: Keycloak OIDC.
- **Grafana**: OIDC SSO with role mapping.
- **Portal**: oauth2-proxy in front of the Astro shell.

In production an external IdP (e.g. Entra ID) federates into Keycloak via
SAML; in this reference, all users live in the local realm for self-contained
demos.

### 4.2 Authorization

OPA (Open Policy Agent) sits in front of every Trino query. The policy
package (`opa-policies-src/trino/`) implements:

- **Catalog/schema gating** — who can `USE` which catalog.
- **Row filters** — predicates injected at query time (e.g. region scope).
- **Column masks** — PII columns hashed/masked unless the role + purpose
  combination allows clear text.
- **Purpose limitation** (GDPR Art. 5(1)(b)) — every query carries a
  `--purpose` session property; OPA verifies the purpose is on the role's
  allow-list for the table.

The OPA `data.json` is generated from
`opa-policies-src/data/role_mappings.json` so role definitions stay
single-sourced (see [ADR-0010](docs/adr/0010-platform-config-single-source.md)).

### 4.3 Roles

Nine personas, four technical + five business:

**Platform team (4):**
`data_engineer`, `data_steward`, `researcher`, `platform_admin`

**Business (5):**
`claims_analyst`, `fraud_analyst`, `marketing_analyst`, `finance_analyst`,
`operations_manager`

Capabilities (catalogs, schemas, purposes, PII/medical/bank visibility,
region filter, break-glass, JIT, four-eyes) are declared per role in
`opa-policies-src/data/role_mappings.json` and rendered as
`platform/10-opa/policies/data.json` for OPA consumption + as
`portal/src/data/role-mappings.generated.json` for the role-aware portal.

### 4.4 Self-service data access

When a user needs access to a dataset outside their role's defaults, they
file an **Access Request Task** in OpenMetadata. The
[`om-access-bridge`](platform/18-om-access-bridge/) listens for approvals,
assigns a `data_access:<catalog>.<schema>` realm role in Keycloak, and OPA
picks up the new role on the next token. See
[ADR-0008](docs/adr/0008-self-service-data-access.md).

---

## 5. Data zones and classification

### 5.1 Classifications

`platform/13-openmetadata-config/classifications.yaml` defines:

- **Confidentiality**: public · internal · confidential · sensitive
- **Personal data**: none · indirect (pseudonymous) · direct (PII)
- **Medical**: yes / no
- **Financial (bank-account)**: yes / no
- **Retention class**: 90d, 1y, 2y, 5y, 7y (audit)
- **Purpose binding**: comma-separated list (`claim_processing`,
  `case_handling`, `enforcement`, `customer_contact`, `proactive_outreach`,
  `quality_control`, `forecasting`, `research`, `*`)

Every dataset in OpenMetadata carries these tags. The OPA bundle reads
classification → purpose mapping from `data.json`.

### 5.2 Data quality

`dbt test`, OpenMetadata's profiler, and per-table data-quality checks feed
a single DQ dashboard. Quality gates run on every dbt build; failures block
downstream marts.

---

## 6. Compliance mapping

| Framework | How the platform supports it |
|---|---|
| **GDPR** (EU 2016/679) | Purpose limitation enforced at query time. PII columns classified + masked. Right-to-be-forgotten via tombstone events + Delta `DELETE`. Data-subject access reports from `customers.created` + access logs. |
| **ISO 27001 / 27002** | Asset inventory in OpenMetadata. Access control via Keycloak realm roles + OPA. Cryptography (TLS everywhere, secrets via Stackable SecretClass). Change management via GitOps. Audit logging in OpenSearch (7-year retention class). |
| **NIS2** (EU 2022/2555) | Incident detection through Prometheus alerts + Vector log shipping to OpenSearch. Network segmentation via NetworkPolicies (one default-deny + selective allows per namespace; see ADR-0009). Supply-chain hygiene via pinned Helm releases + image digests. |
| **EU AI Act** (EU 2024/1689) | Model registry tags in OpenMetadata (algorithm register). Human-in-the-loop checkpoints documented per use case. Risk classification metadata on every model artefact. Sandbox zone for experimental models. |
| **SOC 2** (Trust Services Criteria) | Security/Availability/Confidentiality demonstrated through: Keycloak audit log, Prometheus uptime SLOs, OPA policy unit tests, OPA decision logs, encrypted-at-rest MinIO buckets, four-eyes for sensitive-zone access. |

See [`docs/compliance-mapping.md`](docs/compliance-mapping.md) for the
detailed control-by-control mapping.

---

## 7. Deployment topology

Three deployment modes share the same `platform/` base, distinguished by
overlays:

- **k3d** — single-node developer cluster, host networking, self-signed CA,
  `*.odap.local` ingress.
- **aks** — Azure Kubernetes Service, managed-csi storage, public LB, real
  TLS via cert-manager + DNS-01, ingress on `example.com` (placeholder).
- **stackit** — Gardener-managed SKE on StackIT, yawol load balancer with a
  reserved Floating IP, cert-manager + DNS-01.

Layer order in `platform/` (controlled by `scripts/deploy-platform.sh`):

```
00-namespaces     │ Namespaces + PSA + NetworkPolicy baselines
01-secrets        │ Dev-only secrets (replace in production)
02-authentication │ Keycloak realm + AuthenticationClass for Trino
03-storage        │ MinIO buckets + zone separation
04-zookeeper      │ (off in this release)
05-hive-metastore │ Hive Metastore CRD + Postgres backing store
06-kafka          │ (off in this release)
07-nifi           │ (off in this release)
08-spark          │ SparkApplication CRs + history server
09-trino          │ TrinoCluster + catalogs per zone
10-opa            │ OpaCluster + policy ConfigMap (rendered)
11-airflow        │ AirflowCluster + DAGs (mounted as ConfigMap)
12-superset       │ SupersetCluster + initial dashboards
13-openmetadata-* │ OpenMetadata config: classifications, glossary, init job
14-monitoring     │ Prometheus rules + Alertmanager + Grafana dashboards
15-portal         │ Astro portal Deployment + Ingress
16-jupyter        │ JupyterHub + KubeSpawner + ODAP Lab kernel image
17-multica        │ Multica coding-agent server (exploratory)
18-om-access-bridge │ Self-service access flow
19-nanitics-      │ Nanitics observatory (agent runtime + traces)
20-multica-daemon │ Multica daemon for cluster-side automation
```

---

## 8. Non-goals

- **Real production data.** All datasets are synthetic.
- **Multi-tenant isolation beyond namespace boundaries.** Single-tenant per
  deployment by design.
- **No HA story for stateful components.** Single-replica Trino coordinator,
  single Postgres for HMS, single MinIO node — sufficient for the reference
  but explicitly not productionised.
- **No CDC story.** Source-system change capture is out of scope; the
  reference assumes either batch landings or event-stream producers.

---

## 9. Glossary

| Term | Meaning |
|---|---|
| Bronze / silver / gold / sensitive | Medallion zones in the lakehouse. |
| ODAP | Open Data & Analytics Platform — this reference. |
| OPA | Open Policy Agent — policy engine in front of Trino. |
| Purpose limitation | GDPR Art. 5(1)(b); only use data for the explicitly declared purpose. |
| Sandbox zone | Pseudonymised, researcher-only catalog. |
| Stackable | Operator-based deployment of data products on Kubernetes. |
| Four-eyes | Dual-approval for sensitive operations. |
| Break-glass | Audited emergency access path for `platform_admin`. |

---

## 10. Where to go next

- **Operate the platform**: [`docs/runbook.md`](docs/runbook.md)
- **Add a new component**: read the relevant `platform/NN-*/README.md`
  alongside [`docs/adr/`](docs/adr/) decisions.
- **Add a use case**: copy an existing `dbt/models/marts/uc*/` folder and
  reuse the `_uc*.yml` schema as a template.
- **Add a role**: edit `opa-policies-src/data/role_mappings.json`, run
  `make opa-test`, then `make build-opa-bundle`.
- **Understand a persona's day-to-day**: see the per-role handbooks in
  [`docs/handbooks/`](docs/handbooks/).
