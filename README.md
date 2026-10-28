# Open Data & Analytics Platform

One end-to-end example runs through the whole platform: **Dutch IT Job Market**. Daily vacancy observations from Dutch job sources become governed analytics across **Data, Cloud, SAP, AI, Software and Security**.

The platform connects extraction → MinIO → Spark/Delta → Hive Metastore → Trino/dbt → Superset/Jupyter, scheduled by Airflow and described in OpenMetadata. Keycloak, OPA and platform monitoring support the same journey. NiFi/Kafka and vendor integrations remain optional infrastructure; they are not required by this batch use case.

## Run the example locally

```bash
make jobs-demo     # seven synthetic daily snapshots + SQLite + dashboard export
make jobs-test     # normalization, source-failure, history and quality checks
```

The offline example needs Python 3.11+ and no cluster or API credentials. The portal's `/job-market/` page offers a clearly labelled synthetic sample with domain, date, location and work-mode filters. Every example record carries `is_synthetic=true`; live mode never silently substitutes sample records.

For live extraction, configure the [sources](examples/dutch-it-jobs/sources.json) and provide `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. The adapter uses the Netherlands Adzuna API plus operator-approved RSS/JobPosting sources. Coverage depends on source permissions, available fields and pagination limits. It is not a census of Dutch vacancies.

[Read the complete use-case walkthrough, live setup and data dictionary](docs/use-cases/dutch-it-job-market.md).

## What the example shows

- Daily snapshots, source provenance, conservative cross-source deduplication and repeatable reruns.
- Titles, employers, locations, seniority, skills, languages, education, hours, contracts and work arrangements.
- Original salary units and annual EUR comparisons, with estimated salaries separated from reported pay.
- Job demand, skill demand, geography, work patterns, salary coverage and source quality.
- One set of Bronze, Silver and Gold `job_market` tables, shared by SQL, dashboards, catalog and notebooks.

Multi-domain roles count in each matching domain; domain counts are not additive. A disappearing search result does not establish that a vacancy closed. Historical claims, customer and finance examples are retired under `docs/archive/legacy-examples/` and are not active platform use cases.

## Run it on the platform

```bash
make jobs-image   # build and import odap/job-market:dev into k3d
make jobs-run     # run the complete pipeline on an existing platform
```

Airflow's `dutch_it_jobs_daily` runs at **05:00 Europe/Amsterdam**. Fresh installations default to demo mode; configure live credentials before opting into live extraction. The container runtime runs extraction, Bronze loading, dbt build/tests and catalog publication in sequence. Cloud deployments must publish the runtime image to their registry.

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
make jobs-image
make jobs-run
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

| Directory | Purpose |
|---|---|
| `examples/dutch-it-jobs/` | Daily extraction, deterministic fixtures, normalization and local SQLite analytics |
| `dbt/` | Job-market staging, deduplication, Gold marts, tests and semantic metadata |
| `spark-jobs/` | Bronze Delta loading and lakehouse support |
| `platform/11-airflow/` | Daily job-market orchestration and runtime configuration |
| `platform/12-superset/` | The Dutch IT job-market dashboard |
| `platform/13-openmetadata-config/` | Catalog, glossary, ownership and lineage configuration |
| `platform/16-jupyter/` | The same job-market walkthrough in a notebook |
| `portal/` | Service workspace and interactive `/job-market/` sample explorer |
| `opa-policies-src/` | Trino access policy and tests |
| `docs/` | Active use case, architecture, deployment and decisions |
| `infrastructure/`, `platform-overlays/` | Shared platform infrastructure and environment configuration |

## Documentation

- [Dutch IT Job Market](docs/use-cases/dutch-it-job-market.md)
- [Architecture](docs/architecture/index.md)
- [Runbook](docs/runbook.md)
- [Architecture decisions](docs/adr/index.md)
- [Role handbooks](docs/handbooks/README.md)

This repository is an illustrative reference implementation. Offline records are synthetic. Live collection requires source credentials and appropriate access; no applicant or CV data is collected.

Apache License 2.0 — see [LICENSE](LICENSE).
