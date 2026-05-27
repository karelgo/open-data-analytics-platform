# Open Data & Analytics Platform

Een **fictieve, illustratieve** referentie-implementatie van een modern data-
en analyticsplatform voor UWV, gebouwd op open source en gericht op compliance
met NORA, AVG, BIO/BIO2, NIS2 en de AI Act.

> **Disclaimer.** Geen echte ODAP data, geen echte BSN's, geen echte productiecode.
> Alle datasets zijn synthetisch en gemarkeerd met
> `# SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE`.
> Deze repo is geen ODAP product en geen aanbestedingsstuk.

---

## Wat dit platform doet

Een Kubernetes-native lakehouse + analytics-stack:

- **Storage**: MinIO (S3-compatible).
- **Tabelformaat**: Delta Lake (default voor deze implementatie — zie [ADR-0006](docs/adr/0006-delta-chosen-for-this-implementation.md)). Iceberg-pad blijft afgedekt via abstractie.
- **Catalog backend**: Apache Hive Metastore (Postgres-backed).
- **Ingestion**: file-source → Spark Structured Streaming → Delta op MinIO. NiFi/Kafka-flows zijn als template aanwezig ([`nifi-flows/templates/`](nifi-flows/templates/)) maar de bijbehorende Stackable-operators staan in deze release **uit** — UC-11 leest direct uit de S3 raw-zone.
- **Query engine**: Trino, met OPA-authorisatie (Rego: doelbinding, row filters, column masking).
- **Transformatie**: dbt-trino, format-agnostisch via macro `table_format()`.
- **Orchestratie**: Apache Airflow 3 + astronomer-cosmos voor dbt-DAGs.
- **BI**: Apache Superset.
- **Notebooks**: JupyterHub + KubeSpawner (ODAP Lab) — Python/SQL op alle data-lagen, Git-integratie. Zie [`platform/16-jupyter/`](platform/16-jupyter/).
- **Catalog/governance/lineage/DQ**: OpenMetadata, met een self-service [om-access-bridge](platform/18-om-access-bridge/) (OM task-approval → Keycloak realm-role → OPA grant).
- **AuthN**: Keycloak (OIDC).
- **Portal**: Astro/React workspace-shell die alle service-UIs embed onder één URL ([`portal/`](portal/), [`platform/15-portal/`](platform/15-portal/)).
- **Agent-tooling**: Multica server + Nanitics observatory (zie [`platform/17-multica/`](platform/17-multica/), [`platform/19-nanitics-observatory/`](platform/19-nanitics-observatory/), [`platform/20-multica-daemon/`](platform/20-multica-daemon/)). Exploratory, niet aangesloten op de governance-flow.
- **Logs/metrics/tracing**: Vector + Prometheus; OpenSearch single-node gedeeld voor logs en OM-search. OpenTelemetry-tracing is bekabeld voor support op Trino/Airflow maar nog niet aangesloten op een backend.

Stackable Data Platform-operators in deze release (zie [`infrastructure/stackablectl/release.yaml`](infrastructure/stackablectl/release.yaml)): **airflow, commons, hive, listener, opa, secret, spark-k8s, superset, trino**. NiFi/Kafka/ZooKeeper zijn in [`release.yaml`](infrastructure/stackablectl/release.yaml) **uitgecommentarieerd** — UC-11 vraagt ze niet en ze besparen ~2 vCPU + 4 GiB op k3d.

---

## Snelstart

Het platform draait in drie deployment-modes; alle Make-targets accepteren
`MODE={k3d|aks|stackit}` (default `k3d`). De mode bepaalt:

| Aspect | k3d (default) | aks | stackit |
|---|---|---|---|
| Cluster type | k3d serverlb + local-path | AKS managed-csi + LB | SKE (Gardener) + yawol LB |
| Domain | `odap.local:8443` | `example.com` | `example.com` |
| Storage class | `local-path` | `managed-csi` | `storage-class-ske-csi-cinder` |
| Ingress controller | DaemonSet + hostNetwork | Deployment + LoadBalancer | Deployment + yawol Floating-IP |
| Helm values | `…/values.yaml` + `values-k3d.yaml` | `…/values-aks.yaml` | `…/values-stackit.yaml` |
| Platform overlays | base (flat) | `platform-overlays/aks/<comp>/` | `platform-overlays/stackit/<comp>/` |

### Mode 1 — k3d (developer laptop)

Voorvereisten:

- Docker Desktop met ≥ 8 GB RAM en ≥ 4 CPU's beschikbaar voor containers.
- `k3d` ≥ 5.6, `kubectl` ≥ 1.29, `helm` ≥ 3.14, `stackablectl` ≥ 25.x, `make`.

```bash
# 1. Doctor — controleert tooling + /etc/hosts + kubectl context
make doctor MODE=k3d

# 2. /etc/hosts injectie (vereist sudo, eenmalig)
echo "127.0.0.1 keycloak.odap.local \
  superset.odap.local airflow.odap.local \
  minio.odap.local openmetadata.odap.local \
  jupyter.odap.local platform.odap.local" | sudo tee -a /etc/hosts

# 3. End-to-end deploy (~15-30 min)
make deploy MODE=k3d   # cluster + bootstrap + platform + portal + smoke

# Of stap voor stap:
make cluster MODE=k3d
make bootstrap MODE=k3d
make deploy-platform MODE=k3d
make seed
make test

# 4. Cleanup
make clean
```

### Mode 2 — aks (Azure productie)

```bash
# Vereist: az login, terraform, SP-secret in scripts/azure/env.sh
make doctor MODE=aks
make aks-up           # terraform: AKS + VNet + LB + DNS-zone
make aks-context      # kubeconfig
make aks-all          # bootstrap + deploy + smoke

# Of in CI: gebruik de aks-deploy.yml workflow (handmatige dispatch).
```

### Mode 3 — stackit (StackIT SKE productie)

```bash
# Vereist: stackit CLI + STACKIT_SERVICE_ACCOUNT_TOKEN, terraform.
# Floating IP 188.34.84.39 + DNS-zone example.com worden door
# Terraform beheerd (zie infrastructure/stackit/terraform/).
make doctor MODE=stackit
make stackit-up                              # terraform: SKE + reserved Floating IP
eval "$(make stackit-context)"               # export KUBECONFIG=...
make stackit-all                             # bootstrap + deploy + portal + smoke (~40 min)

# Pauzeren (workers naar 0 — control plane sleeps, PVCs + IP behouden):
make stackit-hibernate
make stackit-wake                            # ~3-5 min terug
make stackit-status                          # HEALTHY / HIBERNATED / RECONCILING

# Of in CI: zie stackit-cd.yml + stackit-smoke.yml workflows.
```

### Mode mismatch-bescherming

`scripts/bootstrap.sh` en `scripts/deploy-platform.sh` weigeren te draaien als
de kubectl-context niet matcht met `--mode`. Een typische foutmelding:

```
FAIL mode=aks but kubectl context 'k3d-odap-platform' is not an AKS cluster.
Run 'make aks-context'.
```


---

## Repository-layout

| Directory | Inhoud |
|---|---|
| `platform-config.yaml` | Centrale configuratie. Wijzig `table_format` hier, niet elders. |
| `docs/` | Architectuur, ADRs, use-case specs, compliance-mapping, runbook. |
| `infrastructure/` | k3d-config, externe Helm-values (cert-manager, Keycloak, MinIO, Postgres, OpenMetadata), Stackable release-pinning. |
| `platform/` | Kubernetes-manifests per laag (00-namespaces … 13-openmetadata-config). |
| `dbt/` | dbt-project, models (staging/intermediate/marts/uc01..uc10), macros, tests. |
| `data-generation/` | Synthetische data-generators (Python). |
| `nifi-flows/` | NiFi-flow templates (iceberg/delta varianten). |
| `spark-jobs/` | PySpark-jobs (streaming + batch + ML demo). |
| `opa-policies-src/` | Rego-policies + tests. |
| `scripts/` | Bash-helpers voor `make`-targets. |
| `tests/` | Smoke / integration / e2e tests. |
| `ci/` | GitHub Actions workflows (in opzet). |

---

## Documentatie

- [Architectuur](docs/architectuur/index.md)
- [Achtergrondsamenvatting](docs/context-summary.md)
- [Compliance-mapping](docs/compliance-mapping.md)
- [Runbook](docs/runbook.md)
- ADRs: [0001](docs/adr/0001-stackable-as-base.md) · [0002](docs/adr/0002-iceberg-vs-delta.md) · [0003](docs/adr/0003-opa-as-trino-authz.md) · [0004](docs/adr/0004-openmetadata-as-catalog.md) · [0005](docs/adr/0005-dbt-trino-as-transform.md) · [0006](docs/adr/0006-delta-chosen-for-this-implementation.md) · [0007](docs/adr/0007-airflow-pipeline-architecture.md) · [0008](docs/adr/0008-self-service-data-access.md) · [0009](docs/adr/0009-networkpolicies-strategy.md) · [0010](docs/adr/0010-platform-config-single-source.md)
- Use cases: [UC-01](docs/use-cases/uc01-claims-funnel.md) · [UC-02](docs/use-cases/uc02-complex-cases-ai.md) · [UC-03](docs/use-cases/uc03-fraud-risk.md) · [UC-04](docs/use-cases/uc04-proactieve-tw.md) · [UC-05](docs/use-cases/uc05-customer-360.md) · [UC-06](docs/use-cases/uc06-schadelast.md) · [UC-07](docs/use-cases/uc07-dq-policies.md) · [UC-08](docs/use-cases/uc08-capacity-planning-planning.md) · [UC-09](docs/use-cases/uc09-reintegration-effect.md) · [UC-10](docs/use-cases/uc10-gegevensdiensten.md) · [UC-11](docs/use-cases/uc11-customer-journey.md) · [UC-12](docs/use-cases/uc12-focus-finops.md)

---

## Status

Werk-in-uitvoering. Zie [WORKLOG.md](WORKLOG.md) voor laatste fase en openstaande
items. De [Definition of Done](docs/architecture.md#definition-of-done) staat
in `docs/architecture.md`.

---

## Licentie

Apache License 2.0 — zie [LICENSE](LICENSE).
