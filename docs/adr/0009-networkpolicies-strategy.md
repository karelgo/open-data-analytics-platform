# ADR-0009: NetworkPolicies — default-deny in cloud, off in k3d

| Status | **Geaccepteerd** |
|---|---|
| Datum | 2026-05-21 |
| Beslissers | Platform Architect, CISO, Platform Admin |
| Gerelateerd | ADR-0001 (Stackable), ADR-0003 (OPA), R-BIO-13 (network segmentation) |

---

## Context

Het platform draait in drie modes (k3d / aks / stackit) en heeft vier
platform namespaces (`odap-platform`, `odap-data`, `odap-meta`, `odap-auth`) plus
`odap-monitoring`. Tot vóór deze ADR was de network-laag **default-allow**:
elke pod in elke namespace kon willekeurig praten met elke andere pod
en uit naar internet.

Voor production is dat in strijd met R-BIO-13 (network segmentation,
zero-trust beginsel). Audit 2026-05 markeerde het als HIGH.

In de developer-cluster (k3d) maakt default-allow het juist mogelijk om
`make seed`, port-forwards en cross-namespace shortcut-tests snel te
laten werken. De Stackable-operators verwachten ook netwerkaccess naar
het bootstrap-Postgres in `odap-data` zonder expliciete annotaties.

## Beslissing

We hanteren een **mode-gesplitste NetworkPolicy-strategie**:

| Mode | NetworkPolicies | Default policy | Source of truth |
|---|---|---|---|
| `k3d` | uit | allow-all | `platform/00-namespaces/` (geen `networkpolicies.yaml`) |
| `aks` | aan | default-deny + namespace-segmentation | `platform-overlays/aks/00-namespaces/networkpolicies.yaml` |
| `stackit` | aan | default-deny + namespace-segmentation | `platform-overlays/stackit/00-namespaces/networkpolicies.yaml` |

Per platform namespace (`odap-platform`, `odap-data`, `odap-meta`, `odap-auth`):

1. `default-deny-all` — `policyTypes: [Ingress, Egress]` met lege podSelector.
2. `allow-dns-egress` — UDP+TCP/53 naar `kube-system/k8s-app=kube-dns`.
3. `allow-intra-namespace` — vrij verkeer binnen dezelfde namespace
   (voorkomt dat we voor elk in-namespace pod-paar een aparte rule
   moeten schrijven).
4. Namespace-specifieke ingress/egress-rules met `namespaceSelector` op
   `kubernetes.io/metadata.name`.

`odap-monitoring` blijft zonder NetworkPolicies — Prometheus/Vector
scrapen elke andere namespace; `odap-platform`/`odap-data`/`odap-meta`/`odap-auth`
laten Prometheus binnen via `allow-from-monitoring`.

## Alternatieven overwogen

1. **Default-deny ook in k3d.** Verworpen: `make seed` (cross-namespace
   Job-naar-MinIO), `make smoke` (port-forwards) en het devcontainer-
   patroon breken. Werkdrukgewin voor één rondreis is groter dan de
   security-gain in een laptop-cluster zonder echte data.
2. **FQDN-egress per pod** (Cilium ClusterwideNetworkPolicy met DNS-
   resolver). Werkt op AKS, niet op StackIT SKE (geen Cilium). Bewaard
   for a latere ADR als we Cilium standardiseren.
3. **Service Mesh (Linkerd / Istio).** Te zwaar for a referentie-
   implementatie. De rules hier blijven onder 100 regels per overlay.

## Consequenties

**Positief:**
- R-BIO-13 voldaan in production-modes.
- Lateral movement na compromise blijft beperkt tot één namespace.
- AuditPolicy in OpenSearch koppelt aan begrensde traffic-flows.

**Negatief / mitigaties:**
- Nieuwe components moeten expliciet egress declareren. Mitigatie:
  iac-validate workflow (zie [`.github/workflows/iac-validate.yml`](../../.github/workflows/iac-validate.yml))
  draait `kustomize build` per overlay; bij missing-rule krijgt de pod
  CrashLoopBackOff. Daarna toevoegen aan `networkpolicies.yaml`.
- Debug-flow: bij blocked traffic in production tail je
  `kubectl logs -n kube-system -l k8s-app=cilium` (AKS) of equivalent
  for the StackIT CNI.

## Migratie & evidence

1. Bestand `platform-overlays/{aks,stackit}/00-namespaces/networkpolicies.yaml`
   bevat de 19 NetworkPolicies (zie `kubectl kustomize` output).
2. Smoke-test in `tests/smoke/` controleert dat default-deny aan staat
   in cloud-modes (TODO — pickup for a volgende sprint).
3. Audit-evidence: `kubectl get networkpolicy -A | wc -l` ≥ 19 in
   cloud-modes; runbook §10.1 mapt dit op R-BIO-13.
