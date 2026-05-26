# 10-opa

Open Policy Agent — authorisatielaag voor Trino (en in toekomst Druid/Kafka).

| Resource | Doel |
|---|---|
| `OpaCluster opa` | 1 OPA-pod (scaled-down). |
| `ConfigMap opa-trino-bundle` (gegenereerd) | Rego-bundle, label `opa.stackable.tech/bundle: "true"` triggert auto-load. |

## Bundle

In fase 3 staat **één** policy in de bundle:

- [`policies/trino-base.rego`](policies/trino-base.rego) — allow-all voor authenticated users (dev bootstrap, ticket `ODAP-PLATFORM-OPA-001`).
- [`policies/trino-base_test.rego`](policies/trino-base_test.rego) — `opa test` coverage.

In fase 9 wordt deze vervangen door de canonical bundle uit `opa-policies-src/trino/`:
- `trino-base.rego` (default-deny)
- `trino-platform-roles.rego` (rol-mapping)
- `trino-doelbinding.rego` (R-AVG-06)
- `trino-row-filters.rego` (R-BIO-11)
- `trino-column-masks.rego` (R-BIO-11)
- + `*_test.rego` per file

## Tests draaien

```bash
opa fmt --diff platform/10-opa/policies/
opa test platform/10-opa/policies/
```

## Apply

```bash
kubectl apply -k platform/10-opa/
```

## Validatie

```bash
kubectl -n odap-platform get opacluster
kubectl -n odap-platform get configmap opa-trino-bundle -o yaml | head
kubectl -n odap-platform get pods -l app.kubernetes.io/name=opa

# Direct OPA-decision testen (in-cluster):
kubectl -n odap-platform run opa-test --rm -it --image=curlimages/curl:8.10.1 --restart=Never -- \
  curl -s -X POST http://opa.odap-platform.svc.cluster.local:8081/v1/data/trino/allow \
       -H 'Content-Type: application/json' \
       -d '{"input":{"context":{"identity":{"user":"data.steward"}},"action":{"operation":"ExecuteQuery"}}}'
# Verwacht: {"result": true}
```

## Productie-pad

- Default-deny in alle base policies; expliciete allow per rol.
- Audit-log per decisie naar OpenSearch.
- ServiceMonitor voor decision-rate / latency-metrics.
- Bundle-validatie in CI: `opa fmt --diff` + `opa test --coverage --fail-on-coverage 80%`.
