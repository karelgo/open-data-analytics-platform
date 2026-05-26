# Deployment modes

The UWV reference platform runs in three modes, selected via `--mode` /
`DEPLOYMENT_MODE` / `make … MODE=…`. The mode is a single switch that drives
hostnames, storage classes, ingress controller shape, and kustomize overlays
end-to-end.

| Aspect | `k3d` (default) | `aks` | `stackit` |
|---|---|---|---|
| Cluster type | k3d serverlb | AKS managed | SKE (Gardener) |
| Browser port | `:8443` (serverlb→443) | `:443` (no port) | `:443` (no port) |
| Domain | `*.odap.local` | `*.example.com` | `*.example.com` |
| Ingress controller | DaemonSet + hostNetwork | Deployment + LoadBalancer | Deployment + yawol-LB on reserved Floating IP 188.34.84.39 |
| Storage class | `local-path` | `managed-csi` (`managed-csi-premium` for MinIO) | `storage-class-ske-csi-cinder` |
| TLS | cert-manager + self-signed CA | cert-manager + Let's Encrypt | cert-manager + Let's Encrypt |
| CoreDNS override | `IN A` + `IN AAAA` template (`*.odap.local` → host IP) | `coredns-custom` ConfigMap | none needed (public DNS) |
| Public DNS | `/etc/hosts` | Azure DNS zone (CNAMEs upserted by aks-deploy.sh) | StackIT DNS zone (`example.com`, managed by Terraform) |
| Hibernate | n/a — destroy + recreate | n/a — SKU-cost-driven | `make stackit-hibernate` / `…-wake` (workers scale to 0, PVCs + IP preserved) |

## Layers

```
┌────────────────────────────────────────────────────────────────────┐
│ User                                                               │
│   make deploy MODE=aks  /  make deploy MODE=k3d                    │
└─────────────┬──────────────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────────────────────────────┐
│ scripts/lib/mode.sh                                                │
│   parse_mode_args         — DEPLOYMENT_MODE, PLATFORM_DOMAIN,      │
│                              PLATFORM_PORT, IS_LOCAL, IS_CLOUD     │
│   require_context         — kubectl context vs mode mismatch       │
│   require_storage_class   — warn if expected SC absent             │
│   chart_value_args <chart> — picks values.yaml + values-<mode>.yaml│
│   kustomize_overlay <comp>— picks platform-overlays/<mode>/<comp>/ │
│                              or platform/<comp>/                   │
└─────────────┬──────────────────────────────────────────────────────┘
              │
   ┌──────────┴──────────────┐
   ▼                         ▼
┌──────────────────────┐   ┌─────────────────────────────────────────┐
│ Helm overlays        │   │ Kustomize overlays                      │
│ infrastructure/helm/ │   │ platform/<comp>/         (base)         │
│   <chart>/           │   │ platform-overlays/<mode>/<comp>/        │
│     values.yaml      │   │   kustomization.yaml                    │
│     values-k3d.yaml  │   │     resources: ../../../platform/<comp> │
│     values-aks.yaml  │   │     patches: [hostname patches, …]      │
└──────────────────────┘   └─────────────────────────────────────────┘
```

## Per-chart helm overlays

Each chart under `infrastructure/helm/<chart>/` has:
- `values.yaml` — mode-agnostic base (credentials, replicas, OIDC config,
  resource requests, image refs)
- `values-k3d.yaml` — k3d-specific overrides (storage class `local-path`,
  hostNetwork ingress controller, KC_HOSTNAME with :8443)
- `values-aks.yaml` — AKS overrides (Azure LoadBalancer, `managed-csi`
  storage, public hostname without :8443, no self-signed CA truststore)

`bootstrap.sh` layers them via `helm upgrade … $(chart_value_args <chart>)`.

## Per-component kustomize overlays

The platform manifests under `platform/<NN>-<comp>/` use a flat layout —
that **is** the k3d base. Mode-specific patches live in a sibling
tree at `platform-overlays/<mode>/<comp>/` (a sibling tree avoids kustomize's
"cycle detected" error that would arise if overlays lived inside their own
base's directory).

Currently `platform-overlays/aks/` and `platform-overlays/stackit/` patch
the public-domain components for their respective hostnames. Adding a new
mode (e.g. EKS or GKE) means copying one of these trees and adjusting the
host strings.

## Adding a new component

1. Drop your manifests in `platform/NN-comp/` with k3d-shaped defaults
   (`.odap.local:8443` hostnames if applicable).
2. If the component needs to change shape per mode, create
   `platform-overlays/aks/NN-comp/kustomization.yaml`:
   ```yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
     - ../../../platform/NN-comp
   patches:
     - target: { kind: Ingress, name: <name> }
       patch: |-
         - op: replace
           path: /spec/rules/0/host
           value: <name>.example.com
         - op: replace
           path: /spec/tls/0/hosts/0
           value: <name>.example.com
   ```
3. Verify with `kubectl kustomize platform-overlays/aks/NN-comp/`.
4. Add the layer to `LAYERS=` in `scripts/deploy-platform.sh` (it's
   automatically picked up by mode-aware deploy via `kustomize_overlay`).

## Adding a new mode

The `stackit` mode was added by following exactly the recipe below; it's
the working template for "add another cloud":

1. Add `MODE` to the case statements in `scripts/lib/mode.sh`
   (`parse_mode_args` + `require_context` + `require_storage_class`).
2. For every chart that has `values-aks.yaml` or `values-stackit.yaml`,
   create a matching `values-<newmode>.yaml`.
3. For every directory that has `platform-overlays/aks/<comp>/` or
   `platform-overlays/stackit/<comp>/`, create
   `platform-overlays/<newmode>/<comp>/` and adjust the host strings.
4. Add a `<newmode>-up` / `<newmode>-bootstrap` / `<newmode>-deploy` /
   `<newmode>-all` target family to the `Makefile` (see the `stackit-*`
   block for a complete example, including `hibernate`/`wake`/`status`).
5. If the mode supports it, also add CI workflows under `.github/workflows/`
   (`<newmode>-cd.yml` + `<newmode>-smoke.yml`).
