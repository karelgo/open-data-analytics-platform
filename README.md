# Open Data & Analytics Platform

A **fictive, illustrative** reference implementation of a modern data and
analytics platform built on open source and designed for compliance with
GDPR, ISO 27001 / 27002, NIS2, the EU AI Act, and SOC 2-aligned controls.

> **Disclaimer.** No real data, no real personal identifiers, no production code.
> All datasets are synthetic and marked with
> `# SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE`.
> This repository is not a product and not a procurement document.

---

## What the platform does

A Kubernetes-native lakehouse + analytics stack:

- **Storage**: MinIO (S3-compatible).
- **Table format**: Delta Lake (default for this implementation — see [ADR-0006](docs/adr/0006-delta-chosen-for-this-implementation.md)). The Iceberg path stays covered through an abstraction.
- **Catalog backend**: Apache Hive Metastore (Postgres-backed).
- **Ingestion**: file-source → Spark Structured Streaming → Delta on MinIO. NiFi/Kafka flows live as templates ([`nifi-flows/templates/`](nifi-flows/templates/)) but the corresponding Stackable operators are **off** in this release — UC-11 reads directly from the S3 raw zone.
- **Query engine**: Trino, with OPA authorization (Rego: purpose limitation, row filters, column masking).
- **Transformation**: dbt-trino, table-format-agnostic through the `table_format()` macro.
- **Orchestration**: Apache Airflow 3 + astronomer-cosmos for dbt DAGs.
- **BI**: Apache Superset.
- **Notebooks**: JupyterHub + KubeSpawner (ODAP Lab) — Python/SQL across all data layers, with Git integration. See [`platform/16-jupyter/`](platform/16-jupyter/).
- **Catalog / governance / lineage / data quality**: OpenMetadata, with a self-service [om-access-bridge](platform/18-om-access-bridge/) (OM task approval → Keycloak realm role → OPA grant).
- **Authentication**: Keycloak (OIDC).
- **Portal**: Astro/React workspace shell that embeds all service UIs under one URL ([`portal/`](portal/), [`platform/15-portal/`](platform/15-portal/)).
- **Agent tooling**: Multica server + Nanitics observatory (see [`platform/17-multica/`](platform/17-multica/), [`platform/19-nanitics-observatory/`](platform/19-nanitics-observatory/), [`platform/20-multica-daemon/`](platform/20-multica-daemon/)). Exploratory, not yet hooked into the governance flow.
- **Logs / metrics / tracing**: Vector + Prometheus; OpenSearch single-node shared between logs and OM search. OpenTelemetry tracing is wired up for Trino/Airflow but not yet connected to a backend.

Stackable Data Platform operators in this release (see [`infrastructure/stackablectl/release.yaml`](infrastructure/stackablectl/release.yaml)): **airflow, commons, hive, listener, opa, secret, spark-k8s, superset, trino**. NiFi/Kafka/ZooKeeper are **commented out** in [`release.yaml`](infrastructure/stackablectl/release.yaml) — UC-11 doesn't need them and skipping them saves ~2 vCPU + 4 GiB on k3d.

---

## Quick start

The platform runs in three deployment modes; all Make targets accept
`MODE={k3d|aks|stackit}` (default `k3d`). The mode controls:

| Aspect | k3d (default) | aks | stackit |
|---|---|---|---|
| Cluster type | k3d serverlb + local-path | AKS managed-csi + LB | SKE (Gardener) + yawol LB |
| Domain | `odap.local:8443` | `example.com` | `example.com` |
| Storage class | `local-path` | `managed-csi` | `storage-class-ske-csi-cinder` |
| Ingress controller | DaemonSet + hostNetwork | Deployment + LoadBalancer | Deployment + yawol Floating-IP |
| Helm values | `…/values.yaml` + `values-k3d.yaml` | `…/values-aks.yaml` | `…/values-stackit.yaml` |
| Platform overlays | base (flat) | `platform-overlays/aks/<comp>/` | `platform-overlays/stackit/<comp>/` |

### Mode 1 — k3d (developer laptop)

Prerequisites:

- Docker Desktop with ≥ 8 GB RAM and ≥ 4 CPUs available to containers.
- `k3d` ≥ 5.6, `kubectl` ≥ 1.29, `helm` ≥ 3.14, `stackablectl` ≥ 25.x, `make`.

```bash
# 1. Doctor — checks tooling + /etc/hosts + kubectl context
make doctor MODE=k3d

# 2. /etc/hosts injection (requires sudo, one-off)
echo "127.0.0.1 keycloak.odap.local \
  superset.odap.local airflow.odap.local \
  minio.odap.local openmetadata.odap.local \
  jupyter.odap.local platform.odap.local" | sudo tee -a /etc/hosts

# 3. End-to-end deploy (~15-30 min)
make deploy MODE=k3d   # cluster + bootstrap + platform + portal + smoke

# Or step by step:
make cluster MODE=k3d
make bootstrap MODE=k3d
make deploy-platform MODE=k3d
make seed
make test

# 4. Cleanup
make clean
```

### Mode 2 — aks (Azure production)

```bash
# Requires: az login, terraform, SP-secret in scripts/azure/env.sh
make doctor MODE=aks
make aks-up           # terraform: AKS + VNet + LB + DNS zone
make aks-context      # kubeconfig
make aks-all          # bootstrap + deploy + smoke

# Or in CI: use the aks-deploy.yml workflow (manual dispatch).
```

### Mode 3 — stackit (StackIT SKE production)

```bash
# Requires: stackit CLI + STACKIT_SERVICE_ACCOUNT_TOKEN, terraform.
# A reserved Floating IP + DNS zone for example.com are managed by Terraform
# (see infrastructure/stackit/terraform/).
make doctor MODE=stackit
make stackit-up                              # terraform: SKE + reserved Floating IP
eval "$(make stackit-context)"               # export KUBECONFIG=...
make stackit-all                             # bootstrap + deploy + portal + smoke (~40 min)

# Pause (workers scale to 0 — control plane sleeps, PVCs + IP retained):
make stackit-hibernate
make stackit-wake                            # ~3-5 min to come back
make stackit-status                          # HEALTHY / HIBERNATED / RECONCILING

# Or in CI: see the stackit-cd.yml + stackit-smoke.yml workflows.
```

### Mode mismatch protection

`scripts/bootstrap.sh` and `scripts/deploy-platform.sh` refuse to run when
the kubectl context doesn't match `--mode`. A typical error:

```
FAIL mode=aks but kubectl context 'k3d-odap-platform' is not an AKS cluster.
Run 'make aks-context'.
```


---

## Repository layout

| Directory | Contents |
|---|---|
| `platform-config.yaml` | Central configuration. Change `table_format` here, not elsewhere. |
| `docs/` | Architecture, ADRs, use-case specs, compliance mapping, runbook. |
| `infrastructure/` | k3d config, external Helm values (cert-manager, Keycloak, MinIO, Postgres, OpenMetadata), Stackable release pinning. |
| `platform/` | Kubernetes manifests per layer (00-namespaces … 13-openmetadata-config). |
| `dbt/` | dbt project, models (staging/intermediate/marts/uc01..uc12), macros, tests. |
| `data-generation/` | Synthetic data generators (Python). |
| `nifi-flows/` | NiFi flow templates (Iceberg / Delta variants). |
| `spark-jobs/` | PySpark jobs (streaming + batch + ML demo). |
| `opa-policies-src/` | Rego policies + tests. |
| `scripts/` | Bash helpers for `make` targets. |
| `tests/` | Smoke / integration / e2e tests. |
| `ci/` | GitHub Actions workflows. |

---

## Documentation

- [Architecture](docs/architecture/index.md)
- [Context summary](docs/context-summary.md)
- [Compliance mapping](docs/compliance-mapping.md)
- [Runbook](docs/runbook.md)
- ADRs: [0001](docs/adr/0001-stackable-as-base.md) · [0002](docs/adr/0002-iceberg-vs-delta.md) · [0003](docs/adr/0003-opa-as-trino-authz.md) · [0004](docs/adr/0004-openmetadata-as-catalog.md) · [0005](docs/adr/0005-dbt-trino-as-transform.md) · [0006](docs/adr/0006-delta-chosen-for-this-implementation.md) · [0007](docs/adr/0007-airflow-pipeline-architecture.md) · [0008](docs/adr/0008-self-service-data-access.md) · [0009](docs/adr/0009-networkpolicies-strategy.md) · [0010](docs/adr/0010-platform-config-single-source.md)
- Use cases: [UC-01](docs/use-cases/uc01-claims-funnel.md) · [UC-02](docs/use-cases/uc02-complex-cases-ai.md) · [UC-03](docs/use-cases/uc03-fraud-risk.md) · [UC-04](docs/use-cases/uc04-eligibility-outreach.md) · [UC-05](docs/use-cases/uc05-customer-360.md) · [UC-06](docs/use-cases/uc06-cost-forecast.md) · [UC-07](docs/use-cases/uc07-dq-policies.md) · [UC-08](docs/use-cases/uc08-capacity-planning.md) · [UC-09](docs/use-cases/uc09-reintegration-effect.md) · [UC-10](docs/use-cases/uc10-data-services.md) · [UC-11](docs/use-cases/uc11-customer-journey.md) · [UC-12](docs/use-cases/uc12-focus-finops.md)

---

## Status

Work in progress. See [WORKLOG.md](WORKLOG.md) for the latest phase and open
items. The [Definition of Done](docs/architecture.md#definition-of-done) lives
in `docs/architecture.md`.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
