# Azure / AKS deployment

Provisioning + deployment of the UWV reference platform on Azure Kubernetes Service.

> Mode selection: the platform now runs uniformly across k3d/AKS via the
> `MODE` Make variable (or `--mode`/`DEPLOYMENT_MODE`). All chart values and
> platform manifests are layered automatically — see [docs/deployment-modes.md](../../docs/deployment-modes.md).
> The AKS path is `make deploy MODE=aks` (or `make aks-all` for the full
> terraform + cluster + smoke flow).

## Layout

```
infrastructure/azure/
├── terraform/             # IaC for the AKS cluster (uses existing RG)
├── letsencrypt-issuer.yaml  # cert-manager ClusterIssuer for *.example.com
├── postgres-create-databases.yaml  # post-bootstrap Job (DB creation workaround)
└── public-ingresses.yaml  # platform-landing Deployment + LE-issued public ingresses
                           # (the rest is now handled by platform-overlays/aks/)

# AKS-specific helm values live alongside the chart bases now:
infrastructure/helm/<chart>/values-aks.yaml

# AKS-specific kustomize overlays:
platform-overlays/aks/<comp>/kustomization.yaml

scripts/azure/
├── env.sh.example         # template for sourcing service-principal creds
├── aks-up.sh              # terraform init + apply
├── aks-context.sh         # az aks get-credentials
├── aks-bootstrap.sh       # thin wrapper → scripts/bootstrap.sh --mode=aks
├── aks-deploy.sh          # thin wrapper → scripts/deploy-platform.sh --mode=aks + AKS post-steps
├── aks-stop.sh            # az aks stop  (deallocate nodes — cost-saving, reversible)
├── aks-start.sh           # az aks start (resume a stopped cluster)
└── aks-down.sh            # terraform destroy (full teardown — zero ongoing cost)
```

## One-time setup

1. Copy and fill in credentials:
   ```bash
   cp scripts/azure/env.sh.example scripts/azure/env.sh
   $EDITOR scripts/azure/env.sh   # paste the SP client_secret
   chmod 600 scripts/azure/env.sh
   ```
2. Copy the tfvars template:
   ```bash
   cp infrastructure/azure/terraform/terraform.tfvars.example \
      infrastructure/azure/terraform/terraform.tfvars
   ```

## Full lifecycle

```bash
# Provision the AKS cluster (~15 min)
make aks-up

# Set local kubectl context
make aks-context

# Install helm charts + Stackable operators
make aks-bootstrap

# Deploy Stackable workloads (Trino, Spark, Kafka, ...)
make aks-deploy

# Run smoke tests
make aks-smoke

# Save costs when done — pick one:
make aks-stop      # deallocates nodes; resume later with `make aks-start`
make aks-down      # terraform destroy; zero ongoing cost
```

`make aks-all` runs up → context → bootstrap → deploy → smoke in one shot.

## Cost (rough, westeurope, on-demand)

- 3× Standard_D8s_v5 (8 vCPU / 32 GB): ~€1.20–1.40 / hour
- AKS control plane (Free tier): €0
- Disks (MinIO PVC + node OS): a few €/month
- LoadBalancer + public IP: €0.025/hour + bandwidth

Total while running: ~**€1.30 / hour**. After `aks-stop` the VMs are deallocated
(no compute charge); only disks remain. After `aks-down` everything terraform
created is gone.

## Security notes

- The SP client secret lives only in `scripts/azure/env.sh` (gitignored) and in
  the AKS cluster object inside Azure. **Rotate it after first use** if the
  secret was ever pasted into chat / a ticket / a screenshot.
- `terraform.tfvars` and `scripts/azure/env.sh` are gitignored. Do not commit.
- For production you would replace the SP cluster identity with a system-assigned
  managed identity and use Azure AD workload identity for in-cluster auth.

## Gotchas worth knowing (lessons from first run)

1. **vCPU quota is the real constraint.** Default subscriptions get only ~10–12
   vCPU per VM family per region. `Standard_D8s_v5` family showed 0 quota in
   westeurope on the dev subscription; switched to `Standard_D8s_v6` (Dsv6 family).
   Check with `az vm list-usage --location westeurope`. Request increases via
   Azure Portal → Quotas; approval can take hours.
2. **AKS Auto-Stop policies.** New clusters in the dev RG started in
   `powerState=Stopped` immediately after provisioning. Likely an Azure Policy
   on the resource group. `az aks start` works, but be aware re-provisioning
   doesn't mean "ready to use" until you confirm `powerState=Running`.
3. **AKS admissions-enforcer vs helm 4 server-side apply.** AKS injects a field
   manager called `admissionsenforcer` onto cert-manager's
   `ValidatingWebhookConfiguration`. Helm 4 (server-side apply by default)
   refuses to upgrade. Fix: `--force-conflicts` on the cert-manager helm install
   (already wired in `scripts/bootstrap.sh`).
4. **Bitnami pulled `bitnami/*` from Docker Hub mid-2025.** All charts that
   pin `image.repository: bitnami/<x>` 404 on pull. The legacy mirror
   `docker.io/bitnamilegacy/*` still serves the old tags. Helm overrides in
   `infrastructure/helm/postgresql/values-aks.yaml` and
   `infrastructure/helm/keycloak/values-aks.yaml` redirect there.
5. **AKS managed disks have a `lost+found` directory at the root.** Bitnami's
   "is this volume empty?" check sees it and goes down the persisted-data path
   even on a brand-new PVC, with side effects in the init flow. Fix: pin
   `persistence.subPath` so the data lands in a subdirectory.
6. **Bitnami postgres in-line `initdb.scripts` block hangs the container's
   init flow on AKS** (clean exit code 2, never reaches the foreground postgres
   process). Workaround: empty the `initdb.scripts` block via override and run
   database creation as a separate Job (`postgres-create-databases.yaml`).

## DNS

The platform's helm-installed UIs (Keycloak, MinIO Console, Grafana, OpenMetadata)
are exposed via ingress-nginx with hostnames under `*.odap.local`.
After bootstrap, point those names at the AKS LoadBalancer IP:

```bash
LB_IP=$(kubectl -n ingress-nginx get svc ingress-nginx-controller \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "$LB_IP keycloak.odap.local minio-console.odap.local \
  grafana.odap.local openmetadata.odap.local" | sudo tee -a /etc/hosts
```

(Smoke tests use in-cluster DNS and don't depend on /etc/hosts.)
