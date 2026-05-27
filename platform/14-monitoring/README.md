# 14-monitoring

Cross-cutting monitoring + reliability resources die niet bij één specifieke
component horen. Toegevoegd in de "quick-wins"-sessie (zie [improvements.md](../../docs/improvements.md)).

| Resource | Improvements # | Doel |
|---|---|---|
| `prometheusrule.yaml` | #5.1 | Metric-alerts: Trino p99, OPA deny-rate, Spark-lag, Postgres-disk, namespace-quota |
| `vector-log-alerts.yaml` | #5.1 | Log-event-alerts: OPA-deny-spike, Trino-access-denied, JVM-OOM, Keycloak-login-error, CSV-upload-fail |
| `podmonitor-vector.yaml` | #5.1 | Laat Prometheus de Vector log-event-counter scrapen op poort 9598 |
| `alertmanager-config.yaml` | #5.9 | Email-receiver (k3d → MailHog, aks → platform relay) + Slack-receiver — secrets in `alertmanager-receivers` |
| `mailhog.yaml` | #5.9 | Dev-only SMTP-sink + web-UI op `mailhog.odap.local`. AKS-overlay verwijdert 'm. |
| `pdb.yaml` | #3 | PodDisruptionBudgets voor alle stateful Stackable-clusters + Postgres + OpenSearch |
| `hpa-trino.yaml` | #3 | HorizontalPodAutoscaler op Trino-workers (1-3 replicas in dev) |
| `opensearch-ilm-job.yaml` | #15 | One-shot Job die ILM-policies toepast: app-logs 30d delete, audit-logs 7 jaar |

## Architecture — alert-pipeline

```
metrics  → Prometheus ─┐
                       ├→ Alertmanager ─→ email (SMTP) ─→ MailHog (k3d) / platform relay (aks)
logs     → Vector  ────┘                  └→ Slack #odap-data-platform
            └─ log_to_metric → alert_event_total{event, namespace, container}
```

- **Metric-alerts**: Prometheus evaluëert `prometheusrule.yaml`.
- **Log-alerts**: Vector's `detect_alert_events`/`log_to_metric` transforms ([infrastructure/helm/vector/values.yaml](../../infrastructure/helm/vector/values.yaml)) detecteren patterns in container-logs en zetten ze om in een counter. Prometheus scrape't via PodMonitor; PrometheusRule `log-events` alerteert op stijging-snelheid.
- **Routing**: AlertmanagerConfig `odap-platform-receivers` stuurt warning + critical naar email **én** Slack (continue: true).

## Prerequisites

- kube-prometheus-stack actief (PrometheusRule + AlertmanagerConfig CRDs).
- Vector geïnstalleerd in `odap-monitoring` namespace (bootstrap fase 11).
- OpenSearch operationeel (`odap-meta` namespace).
- (Voor HPA): metrics-server of prometheus-adapter geïnstalleerd. K3d heeft metrics-server uit; production heeft 'm aan.

## Apply

```bash
# k3d (gebruikt MailHog als SMTP-sink)
kubectl apply -k platform/14-monitoring/

# aks (platform relay i.p.v. MailHog)
kubectl apply -k platform-overlays/aks/14-monitoring/
```

## Validatie

```bash
# Alert-rules in Prometheus
kubectl -n odap-monitoring port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
# → http://localhost:9090/rules  (verwacht: groepen trino, opa, …,
#   log-events met 5 log-event-rules)

# Alertmanager-config geladen
kubectl -n odap-monitoring get alertmanagerconfig
# → odap-platform-receivers (geen status.error)

# Alertmanager-pod runt
kubectl -n odap-monitoring get pods -l app.kubernetes.io/name=alertmanager
# → Running

# MailHog runt (k3d)
kubectl -n odap-monitoring get pods -l app.kubernetes.io/name=mailhog

# End-to-end: stuur synthetische alert
make alert-test
# k3d : check https://mailhog.odap.local:8443/
# aks : check platform-alerts@example.com inbox

# PDBs
kubectl get pdb -A | grep uwv

# HPA-status
kubectl -n odap-platform get hpa

# ILM-job complete
kubectl -n odap-meta logs job/opensearch-ilm-bootstrap
```

## Production checklist (AKS)

- [ ] `alertmanager.enabled: true` in helm-values (al gezet in `values-aks.yaml`).
- [ ] Slack-webhook + SMTP-password via External Secrets Operator uit Vault (nu: handmatige patch in `platform-overlays/aks/14-monitoring/secret-smtp-prod.yaml`).
- [ ] `smarthost`/`from`/`to` in `alertmanager-smtp-prod.yaml` aanpassen naar echte platform relay coordinates.
- [ ] PagerDuty re-enablen (CRD-schema fix — zie comment in `alertmanager-config.yaml`).
- [ ] HPA `maxReplicas: 10+`.
- [ ] ILM-policies: pas index-rollover-tresholds aan op verwacht volume.

## Customisatie

**Een nieuwe alert toevoegen (metric-based):**

Edit [prometheusrule.yaml](prometheusrule.yaml), voeg een rule toe aan een bestaande group of nieuwe group. `severity: warning|critical` bepaalt het routing-path. `component` label wordt door inhibitRules gebruikt.

**Een nieuwe alert toevoegen (log-based):**

1. Edit [infrastructure/helm/vector/values.yaml](../../infrastructure/helm/vector/values.yaml) → `detect_alert_events`, voeg een `if contains(...) { .alert_event = "<naam>" }` regel toe.
2. Edit [vector-log-alerts.yaml](vector-log-alerts.yaml), voeg een rule met `vector_alert_event_total{event="<naam>"}` toe.
3. `helm upgrade vector …` + `kubectl apply -k platform/14-monitoring/`.

**Een receiver toevoegen (bijv. Teams-webhook):**

Edit [alertmanager-config.yaml](alertmanager-config.yaml), voeg een entry toe aan `spec.receivers` (zie [AlertmanagerConfig CRD-docs](https://prometheus-operator.dev/docs/api-reference/api/#monitoring.coreos.com/v1alpha1.AlertmanagerConfig)) en voeg een route toe.
