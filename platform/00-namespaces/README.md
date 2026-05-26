# 00-namespaces

Declaratieve namespaces voor het ODAP platform. Ook door
`scripts/bootstrap.sh` (Helm) idempotent aangemaakt; dit bestand is canonical.

| Namespace | Inhoud |
|---|---|
| `odap-platform` | Stackable workloads: ZK, HMS, Kafka, NiFi, Spark, Trino, OPA, Airflow, Superset |
| `odap-data` | Gedeelde Postgres-instance |
| `odap-meta` | OpenMetadata + OpenSearch |
| `odap-monitoring` | kube-prometheus-stack (Prometheus, Grafana) |
| `odap-auth` | Keycloak |

Labels (`odap.io/*`) worden door OpenMetadata's Kubernetes-connector (fase 8)
opgepikt voor governance-context.

## Apply

```bash
kubectl apply -k platform/00-namespaces/
```
