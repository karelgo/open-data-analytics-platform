# scripts/ — Shell + Python helpers

Alle scripts worden aangeroepen via [`make`](../Makefile)-targets in de
top-level `Makefile`. Ze zijn **idempotent en herstartbaar** — opnieuw
draaien doet geen schade.

> Direct aanroepen mag ook (`bash scripts/<x>.sh`), maar `make` zet
> environment-variabelen (`TABLE_FORMAT`, `CLUSTER_NAME`) correct.

## Lifecycle (lokale k3d)

| Script | Make-target | Doel |
|---|---|---|
| [`cluster.sh`](cluster.sh) | `make cluster` | Maak k3d-cluster aan. Idempotent — bestaande cluster wordt hergebruikt. |
| [`bootstrap.sh`](bootstrap.sh) | `make bootstrap` | Installeer Helm-charts: cert-manager, MinIO, Postgres, Keycloak, OpenSearch, Stackable-operators. |
| [`render-trino-catalogs.py`](render-trino-catalogs.py) | `make render-catalogs` | Render Trino-catalog templates op basis van `platform-config.yaml` (delta vs iceberg). |
| [`deploy-platform.sh`](deploy-platform.sh) | `make deploy-platform` | Pas `platform/00`..`15` toe in volgorde. |
| [`build-opa-bundle.sh`](build-opa-bundle.sh) | `make opa-bundle` | Test + bundle Rego-policies en sync ze naar `platform/10-opa/policies/`. |
| [`seed.sh`](seed.sh) | `make seed` | Genereer + laad synthetische data via een Kubernetes Job (10k cliënten default). |
| [`run-smoke-tests.sh`](run-smoke-tests.sh) | `make smoke` / `make test` | Run alle smoke-tests onder `tests/smoke/`. |
| [`clean.sh`](clean.sh) | `make clean` | Verwijder de k3d-cluster volledig. |
| [`full-deploy.sh`](full-deploy.sh) | — | Alles-in-één: cluster + bootstrap + deploy + seed + smoke. |

## Operationeel

| Script | Make-target | Doel |
|---|---|---|
| [`doctor.sh`](doctor.sh) | `make doctor` | Check vereiste tooling op de host (docker, k3d, kubectl, helm, stackablectl, opa, yq, …). |
| [`port-forward.sh`](port-forward.sh) | `make forward` | Start `kubectl port-forward` voor service-UI's die niet via ingress lopen. PIDs in `/tmp/pf-*.pid`. |

## AKS (Azure)

Voor de Azure-variant. Zie [`infrastructure/azure/README.md`](../infrastructure/azure/README.md) voor de volledige flow.

| Script | Make-target | Doel |
|---|---|---|
| [`azure/aks-up.sh`](azure/aks-up.sh) | `make aks-up` | `terraform apply` — provision AKS in bestaande RG. |
| [`azure/aks-context.sh`](azure/aks-context.sh) | `make aks-context` | `az aks get-credentials` — kubectl-context op AKS zetten. |
| [`azure/aks-bootstrap.sh`](azure/aks-bootstrap.sh) | `make aks-bootstrap` | Helm-charts + Stackable-operators op AKS. |
| [`azure/aks-deploy.sh`](azure/aks-deploy.sh) | `make aks-deploy` | Platform-manifests deployen op AKS. |
| [`azure/aks-stop.sh`](azure/aks-stop.sh) | `make aks-stop` | `az aks stop` — nodes deallocaten, reversible. |
| [`azure/aks-start.sh`](azure/aks-start.sh) | `make aks-start` | Resume een gestopt cluster. |
| [`azure/aks-down.sh`](azure/aks-down.sh) | `make aks-down` | `terraform destroy` — volledige teardown. |
| `azure/env.sh` | — | Service-principal credentials. **Niet committen.** Begin met `azure/env.sh.example`. |

## Conventies

- Bash: `set -euo pipefail` aan de top, kleurige `log()`/`warn()`/`fail()`-helpers.
- Idempotent: `kubectl apply` (geen `create`), `helm upgrade --install`,
  `if exists then skip`.
- Output begint met `==> <stap>` en eindigt met `OK <stap>` voor scripted runs.
- Geen geheimen in scripts — read uit Kubernetes Secret of `az keyvault`.

## Eerste run (happy path)

```bash
make doctor              # check tooling
make cluster             # k3d cluster create
make bootstrap           # helm charts
make deploy-platform     # alle platform/-manifests
make seed                # synthetische data
make smoke               # rook-tests
```

Of in één keer:

```bash
bash scripts/full-deploy.sh
```
