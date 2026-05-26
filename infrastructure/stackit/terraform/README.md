# StackIT SKE — Phase 0 Terraform

Provisions:
- 1 × SKE cluster (default: 3 × g2i.8 nodes in eu01-3)
- 1 × Reserved Floating IP for the ingress controller
- An admin kubeconfig written to `kubeconfig.yaml` (24h validity)

## Prerequisites

- Terraform ≥ 1.5
- A StackIT service account JSON key stored locally (created in the StackIT portal → IAM → Service Accounts)
- The service account needs project-level permissions for SKE + IaaS (public IP)

## Authentication

The `stackitcloud/stackit` provider reads the service account key from an env var:

```bash
export STACKIT_SERVICE_ACCOUNT_KEY_PATH="$HOME/.config/stackit/sa-key.json"
```

If you put the key elsewhere, point the env var at it. **Never** commit the key file.

## Usage

```bash
cd infrastructure/stackit/terraform

terraform init
terraform plan
terraform apply
```

After apply completes:

```bash
# Floating IP — paste into Azure DNS A records for example.com + *.example.com
terraform output floating_ip

# Use the generated kubeconfig
export KUBECONFIG="$(terraform output -raw kubeconfig_absolute_path)"
kubectl get nodes
```

## After 24 hours

The admin kubeconfig expires. Re-mint it:

```bash
terraform apply -refresh-only -auto-approve
# or simply
terraform apply
```

The Floating IP and cluster are NOT recreated — only the kubeconfig.

## Resource sizing

Default is 3 nodes × g2i.8 (8 vCPU, 32 GB each) = 24 vCPU / 96 GB, single AZ (eu01-3). This matches the AKS profile (3 × Standard_D8s_v5).

To go bigger or HA:

```hcl
node_machine_type       = "g2i.16"                     # 16 vCPU / 64 GB
node_availability_zones = ["eu01-1","eu01-2","eu01-3"] # 3-AZ spread, nodes-per-AZ = node_minimum / 3
```

## What this module does NOT create

- DNS zone (lives in Azure — `dev-stackable-rg` / `example.com`)
- Object storage (Phase 2 deploys MinIO in-cluster, same pattern as AKS)
- Container registry (use `ghcr.io` or push to StackIT registry separately)
- Observability instance (Phase 2 deploys Prometheus + OpenSearch in-cluster)

## Destroy

```bash
terraform destroy
```

The Floating IP is released back to the StackIT pool — your DNS records will then point at nothing. If you want to keep the IP across cluster rebuilds, mark it `prevent_destroy = true` in `network.tf`.
