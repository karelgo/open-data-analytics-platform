# Verbeteringen — Roadmap for the Open Data & Analytics Platform

Status: **post-fase-10 audit** (2026-05-01). Deze lijst is geen verplichting,
maar inventariseert verbeterruimte op alle vlakken: security, betrouwbaarheid,
performance, observability, compliance, data-kwaliteit, dev-ex en
architecture.

**Update 2026-05-11** — self-service data access opgepakt via
[ADR-0008](adr/0008-self-service-data-access.md): nieuwe service
`platform/18-om-access-bridge/` brugt OpenMetadata Request Access-Tasks naar
Keycloak realm-roles; OPA-Rego herkent `data_access:<catalog>.<schema>`
als grant. Punt 1.2 (`gdpr_request`) blijft open — access-request-flow ≠
inzage-/wisrecht-flow.

**Notatie**:

- **Prio**: 🔴 production-blocker · 🟠 hoog-waarde · 🟡 polish
- **Effort**: S (≤ 1 dag) · M (1–3 dagen) · L (1 week) · XL (> 1 week)

---

## 1. Concrete gaps gemeten in code

Deze items zijn in deze repo **fysiek afwezig** en zijn de eerste kandidaten
voor opvolg-werk.

| # | Item | Locatie | Prio | Effort |
|---|---|---|---|---|
| 1.1 | **4 mart-directories leeg**: UC-02, UC-03, UC-08, UC-10 (UC-09 is opgeleverd als `uc09_reintegration_effect`) | `dbt/models/marts/uc{02,03,08,10}*/` | 🟠 | M |
| 1.2 | **`gdpr_request` DAG ontbreekt** ondanks referentie in [compliance-mapping R-AVG-10](compliance-mapping.md) — inzage- en wisrecht-flow. (Self-service *access-request* is sinds ADR-0008 wél aanwezig — andere R-AVG-10-aspect.) | `platform/11-airflow/dags/` | 🔴 | M |
| 1.3 | **Geen NetworkPolicies** — pods kunnen vrij cross-namespace praten | `platform/00-namespaces/` | 🔴 | M |
| 1.4 | **Geen HPA** — PDBs voor Stackable-producten (kafka/hive/zk/trino/nifi/airflow/superset) worden through the operators zelf gemaakt; resterende gap is HPA + PDBs voor niet-Stackable components | `platform/*/` | 🟠 | S |
| 1.5 | ~~Geen ResourceQuota / LimitRange per namespace~~ — opgelost in [`platform/00-namespaces/resourcequota-limitrange.yaml`](../platform/00-namespaces/resourcequota-limitrange.yaml) | `platform/00-namespaces/` | ✅ | — |
| 1.6 | **Geen pre-built Superset-dashboards** — DoD-anchor "WIA Funnel" niet voltooid | `platform/12-superset/dashboards/` | 🟠 | M |
| 1.7 | **Geen kustomize `overlays/`** — geen prod-overlay om scaled-down naar production-replicas te flippen | `platform/*/overlays/` | 🟠 | M |
| 1.8 | ~~Geen Prometheus AlertRules~~ — opgelost in [`platform/14-monitoring/prometheusrule.yaml`](../platform/14-monitoring/prometheusrule.yaml); zie runbook §9 voor log-based + metric-based alerts | `platform/14-monitoring/` | ✅ | — |
| 1.9 | **Geen Grafana-dashboards UWV-specifiek** — alleen de defaults uit kube-prometheus-stack | `infrastructure/helm/prometheus-stack/` | 🟡 | M |
| 1.10 | **Geen KafkaTopic CRDs** — `auto.create.topics=true` in dev | `platform/06-kafka/` | 🟠 | S |
| 1.11 | **`pseudonymize.sql` macro nergens gebruikt** in de dbt-models | `dbt/models/` | 🟡 | S |
| 1.12 | **UC-02 placeholder-mart absent** ondanks vermelding in [`docs/use-cases/uc02-complex-cases-ai.md`](use-cases/uc02-complex-cases-ai.md) | `dbt/models/marts/uc02_complex_cases/` | 🟡 | S |
| 1.13 | **`tests/integration/` is leeg** — alleen smoke + e2e | `tests/integration/` | 🟡 | M |
| 1.14 | **`platform/13-openmetadata-config/ingestion-pipelines/` is leeg** — directory aangemaakt, geen content | — | 🟡 | S |
| 1.15 | **Geen pre-commit hooks** ondanks vermelding in master-prompt §4 (`pre-commit-config.yaml`) | repo-root | 🟡 | S |
| 1.16 | **Geen `SECURITY.md`** voor vulnerability disclosure (R-NIS2-05) | repo-root | 🟠 | S |
| 1.17 | **Geen `CHANGELOG.md`** — alleen [WORKLOG.md](../WORKLOG.md) als sessie-log | repo-root | 🟡 | S |
| 1.18 | **Geen `CONTRIBUTING.md`** — flow voor toevoegen UC / generator / policy ontbreekt | repo-root | 🟡 | M |

---

## 2. Security

### 2.1 Secret management

| # | Item | Prio | Effort |
|---|---|---|---|
| 2.1.1 | **SOPS / SealedSecrets** voor committed secrets — nu plaintext in `dev-secrets.yaml` | 🔴 | M |
| 2.1.2 | **External Secrets Operator + Vault** voor production | 🔴 | L |
| 2.1.3 | **Secret-rotatie** — Stackable secret-operator kan TLS-certs roteren maar credentials niet | 🟠 | M |
| 2.1.4 | **JWT-token bootstrap automatiseren** — nu manueel `metadata generate-token` na bootstrap | 🟠 | S |
| 2.1.5 | **Per-OIDC-client unique secrets** — nu allemaal `odap-dev-only-CHANGE-ME-<service>-secret`; production roteert via Keycloak admin-API | 🟠 | M |

### 2.2 TLS / encryptie

| # | Item | Prio | Effort |
|---|---|---|---|
| 2.2.1 | **MinIO TLS aanzetten** — `tls.enabled: false` in [values.yaml](../infrastructure/helm/minio/values.yaml). Production: client-CA + server-cert via cert-manager | 🔴 | S |
| 2.2.2 | **Vector → OpenSearch over TLS + auth** — nu plaintext HTTP | 🔴 | S |
| 2.2.3 | **Spark s3a-connectie**: `fs.s3a.connection.ssl.enabled=false`. Production: CA-truststore mounten | 🔴 | S |
| 2.2.4 | **trust-manager Bundle** voor CA-distributie naar alle namespaces — runbook documenteert handmatige kopie | 🟠 | M |
| 2.2.5 | **Pod-to-pod mTLS** via Stackable's `tls-internal` SecretClass — voorbereid maar niet geactiveerd | 🟠 | L |
| 2.2.6 | **HSTS + Content-Security-Policy** op ingress-nginx | 🟡 | S |

### 2.3 Authenticatie

| # | Item | Prio | Effort |
|---|---|---|---|
| 2.3.1 | **MFA/TOTP verplicht** voor admin-rollen in Keycloak — `requiredActions: ["CONFIGURE_TOTP"]` toevoegen aan realm-export | 🔴 | S |
| 2.3.2 | **WebAuthn/passkeys** voor `platform_admin` | 🟠 | M |
| 2.3.3 | **Sessietimeouts** in realm — nu defaults | 🟡 | S |
| 2.3.4 | **DigiD/eHerkenning federatie-stub** in Keycloak realm — referentie noemt het, geen voorbeeld | 🟡 | M |
| 2.3.5 | **`smoketest`-static-auth verwijderen** in production-overlay — CI-check dat het er niet bij staat | 🟠 | S |

### 2.4 Authorisatie / OPA

| # | Item | Prio | Effort |
|---|---|---|---|
| 2.4.1 | **OPA decision-log naar OpenSearch** — Stackable OPA ondersteunt `decisionLogs.console: true`; pipe via Vector | 🔴 | M |
| 2.4.2 | **4-eyes voor `sensitive.*`** — gedocumenteerd in UC-02 spec, niet afgedwongen in Rego | 🟠 | L |
| 2.4.3 | **JIT-access voor `data_engineer`** — `jit_required: true` in role-mapping, geen TTL-mechanisme | 🟠 | L |
| 2.4.4 | **Break-glass logging** — `platform_admin` zou elk gebruik moeten loggen + Slack-alert | 🟠 | M |
| 2.4.5 | **Policy voor write-ops uitwerken** — nu alleen `data_engineer` + `platform_admin` mogen schrijven; geen tests voor specifieke schrijf-paden | 🟠 | M |
| 2.4.6 | **Verplicht regio-attribuut voor claims_analyst** — als `extraCredentials.regio` ontbreekt, deny i.p.v. fall-back-no-filter | 🟠 | S |
| 2.4.7 | **OPA bundle-coverage > 80%** — `opa test --coverage` toevoegen aan CI | 🟡 | S |
| 2.4.8 | **Reverse-metadata OM → OPA** — OM tags `Purpose limitation.*` als bron voor `resource_purposes` (vervangt hardcoded data.json) | 🟠 | XL |

### 2.5 Netwerk-segmentatie

| # | Item | Prio | Effort |
|---|---|---|---|
| 2.5.1 | **NetworkPolicy per namespace** — `odap-platform` mag alleen praten naar `odap-data` (DB) en `odap-meta` (OM) | 🔴 | M |
| 2.5.2 | **Cilium of Calico** voor L7-NetworkPolicies (production) | 🟡 | L |
| 2.5.3 | **Egress-filtering** — pods mogen alleen externe images + Kafka producers van bron-mocks bereiken | 🟠 | M |
| 2.5.4 | **MinIO en OpenSearch in private VPC** in production — niet via ingress-nginx | 🟠 | M |

### 2.6 Container-/supply-chain-security

| # | Item | Prio | Effort |
|---|---|---|---|
| 2.6.1 | **`cosign verify` uitbreiden naar alle Stackable-images** in CI — nu één sample | 🟠 | S |
| 2.6.2 | **Trivy fail-on-severity** — security-scan.yml heeft `severity: HIGH,CRITICAL` maar geen exit-code-fail | 🟠 | S |
| 2.6.3 | **SBOM voor onze eigen artefacten** — dbt-package, data-generation, spark-jobs | 🟡 | M |
| 2.6.4 | **dbt packages-pinning met checksum** — packages.yml pint versie maar niet checksum | 🟡 | S |
| 2.6.5 | **Renovate / Dependabot** voor dep-updates | 🟡 | S |

### 2.7 Data-security

| # | Item | Prio | Effort |
|---|---|---|---|
| 2.7.1 | **Pseudonymize-macro daadwerkelijk gebruiken** — in `mart_uc09_*` (sandbox) en `silver.customers.*` waar PII niet primair-proces is | 🔴 | M |
| 2.7.2 | **Trino event-listener naar Kafka** voor query-history → audit-log naar OpenSearch | 🟠 | M |
| 2.7.3 | **MinIO Object-Lock** voor immutable backups (R-BIO-23) | 🟠 | S |
| 2.7.4 | **Sensitive Vault aparte encryption-key** — nu zelfde KMS/MinIO-credentials als bronze | 🔴 | L |

---

## 3. Betrouwbaarheid / Resilience

### 3.1 Hoge beschikbaarheid

| # | Item | Prio | Effort |
|---|---|---|---|
| 3.1.1 | **Postgres HA** — production-overlay met cnpg-operator (CloudNativePG) of Zalando-postgres | 🔴 | L |
| 3.1.2 | **MinIO distributed mode** — minimaal 4 nodes met EC | 🔴 | L |
| 3.1.3 | **OpenSearch ≥ 3 master + dedicated data-tier** | 🟠 | M |
| 3.1.4 | **Kafka ≥ 3 brokers** met `min.insync.replicas=2` | 🔴 | M |
| 3.1.5 | **ZooKeeper ≥ 3 servers** voor quorum | 🟠 | S |
| 3.1.6 | **Trino ≥ 2 coordinators** (HA via Stackable's coordinator-role) | 🟠 | M |
| 3.1.7 | **Airflow ≥ 2 webservers + 2 schedulers** | 🟠 | S |

### 3.2 Resilience-patterns

| # | Item | Prio | Effort |
|---|---|---|---|
| 3.2.1 | **Dead-Letter Queue (DLQ)** voor Spark streaming — failed records → `<domain>.<domain>.<event>.dlq` | 🟠 | M |
| 3.2.2 | **Retries + circuit-breakers** in spark-jobs voor transiente Kafka/HMS-issues | 🟡 | S |
| 3.2.3 | **PodDisruptionBudgets** voor alle Stackable-clusters | 🟠 | S |
| 3.2.4 | **HorizontalPodAutoscaler** voor Trino-workers + Spark-executors (gebaseerd op CPU/queue-depth) | 🟡 | M |
| 3.2.5 | **Spark Streaming `failOnDataLoss: true`** in production i.p.v. nu `false` | 🟡 | S |
| 3.2.6 | **Kafka topic-replication-factor 3** — nu RF=1 dev-only | 🔴 | S |

### 3.3 Backup / recovery

| # | Item | Prio | Effort |
|---|---|---|---|
| 3.3.1 | **Backup-Job CronJob** in `odap-data` — nu manueel via runbook | 🔴 | M |
| 3.3.2 | **Restore-test-script** dat backup-restore daadwerkelijk valideert | 🔴 | M |
| 3.3.3 | **Off-site / cross-region backup** voor production — out-of-scope dev | 🟠 | L |
| 3.3.4 | **MinIO bucket-versioning** voor accidentele deletes | 🟠 | S |
| 3.3.5 | **Velero** voor K8s-resource backup (config + Secrets) | 🟡 | M |

### 3.4 Chaos-engineering

| # | Item | Prio | Effort |
|---|---|---|---|
| 3.4.1 | **Chaos-tests** met Chaos Mesh — kill random pod, observeer recovery | 🟡 | M |
| 3.4.2 | **DR-exercise script** — gameday: simuleer regio-failure | 🟡 | L |

---

## 4. Performance / Schaal

| # | Item | Prio | Effort |
|---|---|---|---|
| 4.1 | **Production-overlay met scaled-up resources** — kustomize `overlays/production/` met groter CPU/RAM | 🟠 | M |
| 4.2 | **Iceberg vs Delta benchmark** — concrete script dat per-format-keuze meetbaar maakt | 🟡 | M |
| 4.3 | **Trino result-cache** + workload-isolation (resource-groups) | 🟡 | M |
| 4.4 | **dbt-marts partitionering verbeteren** — UC-04 / UC-05 / UC-07 missen partition_columns hint | 🟡 | S |
| 4.5 | **Z-ordering / Liquid clustering** voor Delta cliëntscan-tabellen | 🟡 | M |
| 4.6 | **Spark Streaming-lag metrics** + alerts | 🟠 | S |
| 4.7 | **Trino query-result-cache** via Memcached / Redis | 🟡 | M |
| 4.8 | **dbt incremental-models** — nu materialized=table; voor grote marts 'incremental' overwegen | 🟡 | M |
| 4.9 | **Spark Adaptive Query Execution AAN** — `spark.sql.adaptive.enabled=true` | 🟡 | S |
| 4.10 | **Connection-pooling** in dbt-trino runs (PoolableConnection driver) | 🟡 | S |

---

## 5. Observability

| # | Item | Prio | Effort |
|---|---|---|---|
| 5.1 | **Prometheus AlertRules** — basis-set in [prometheusrule.yaml](../platform/14-monitoring/prometheusrule.yaml) (Trino, OPA, Spark-lag, Postgres, kube-state). Uitbreiding (2026-05-18): log-based alerts via Vector → log_to_metric ([vector-log-alerts.yaml](../platform/14-monitoring/vector-log-alerts.yaml)): OPA-deny-spike, Trino access-denied-spike, JVM-OOM, Keycloak-login-error, CSV-upload-fail. | ✅ | done |
| 5.2 | **Grafana-dashboards UWV** — per UC één + platform-overview | 🟠 | L |
| 5.3 | **OpenSearch ILM-policy** — hot/warm/cold tier voor `logs-*` | 🟠 | S |
| 5.4 | **OpenSearch Dashboards installeren** — log-querying-UI | 🟡 | M |
| 5.5 | **Distributed tracing** (Jaeger of Tempo) — Trino/Spark ondersteunen OpenTelemetry-spans | 🟡 | L |
| 5.6 | **Logs-naar-OS schemamapping** — Vector schrijft nu raw; ECS- of OTel-logs-format zou queries beter maken | 🟡 | M |
| 5.7 | **OpenMetadata observability-tab** — DQ-test-resultaten + lineage-events live | 🟡 | M |
| 5.8 | **SLO-definities + SLI's** — start met uptime + DQ + ingestion-latency per data-product | 🟠 | M |
| 5.9 | ~~**Alertmanager met Slack/PagerDuty**~~ — opgepakt 2026-05-18: email-receiver toegevoegd ([alertmanager-config.yaml](../platform/14-monitoring/alertmanager-config.yaml)) + MailHog als k3d-SMTP-sink + AKS-overlay voor platform relay. Slack-receiver was er al. PagerDuty blijft uitgeschakeld tot CRD-schema fix. | ✅ | done |
| 5.10 | **Loki of OpenSearch query-saver** voor frequente debug-queries | 🟡 | S |

---

## 6. Compliance & Governance

| # | Item | Prio | Effort |
|---|---|---|---|
| 6.1 | **DPIA template** in `docs/dpia/uc02-complex-cases.md` — nu enkel placeholder-link | 🔴 | M |
| 6.2 | **IAMA template** in `docs/iama/` voor UC-02/UC-03 | 🔴 | M |
| 6.3 | **`gdpr_request` DAG** — geautomatiseerde inzage/correctie/verwijdering per BSN | 🔴 | L |
| 6.4 | **Retention period-DAG** — drop records ouder dan `meta.retention period_jaren` | 🔴 | M |
| 6.5 | **Audit-log retention 7 jaar** — ILM-policy op `logs-audit-*` apart van app-logs | 🟠 | S |
| 6.6 | **OPA decision-log → OpenSearch + 7-jaar-retention** | 🔴 | M |
| 6.7 | **Quarterly access-review-script** — exporteert role-mappings + Keycloak-users naar Excel voor manager-bevestiging | 🟠 | M |
| 6.8 | **Algoritmeregister-export** — JSON-feed met alle `meta.risk_tier=hoog` models | 🟠 | M |
| 6.9 | **Processingsregister art. 30** export uit OM custom-properties (R-AVG-02) | 🟠 | M |
| 6.10 | **`make compliance-evidence`** — gebundelde tar met opa-test-rapport + OM-classifications + dbt-test-resultaten | 🟠 | M |
| 6.11 | **Reproduceerbaarheid van scenario-runs** UC-06 — hash van inputs + scenario opnemen in elk run-record | 🟡 | S |
| 6.12 | **Policy-coverage-rapport** — welke catalog/schema/table heeft géén `meta.purpose-limitation` (en zou dat eigenlijk wel moeten hebben)? | 🟠 | S |

---

## 7. Data / Analytics

### 7.1 Generators

| # | Item | Prio | Effort |
|---|---|---|---|
| 7.1.1 | **Realistische cross-domein-relaties** — een WW-aanvraag refereert nu aan een random BSN i.p.v. één with a recente afsluiting van een dienstverband | 🟠 | M |
| 7.1.2 | **Stress-volume-tests** (1M cliënten) | 🟡 | S |
| 7.1.3 | **Tijdsverloop simuleren** — niet alleen "snapshot maken" maar event-stream over 30 dagen | 🟠 | M |
| 7.1.4 | **PII-detectie-test** met opzettelijk-ingespoten edge-cases (BSN-look-alike, etc.) | 🟡 | S |
| 7.1.5 | **CBS-microdata-mockup** voor UC-06 macro-trend models | 🟡 | M |

### 7.2 dbt models

| # | Item | Prio | Effort |
|---|---|---|---|
| 7.2.1 | **5 ontbrekende mart-folders invullen** (UC-02/03/08/09/10) — nu alleen specs | 🟠 | L |
| 7.2.2 | **dbt snapshots** — SCD-2 voor dossier-status, claim payout-status | 🟡 | M |
| 7.2.3 | **dbt-expectations toevoegen** — meer regel-based DQ (tussen-tabellen, conditional checks) | 🟡 | M |
| 7.2.4 | **dbt sources `freshness` checks** — alarmeer als bronze-tabel > 1u geen nieuwe rij heeft | 🟠 | S |
| 7.2.5 | **dbt-meta-block CI-check** — script dat alle marts verplichte `meta`-keys hebben (legal_basis, purpose-limitation, retention period, eigenaar, risk_tier) | 🟠 | S |
| 7.2.6 | **Macro `apply_purpose-limitation_tag` daadwerkelijk SQL emitteren** — nu no-op | 🟡 | S |
| 7.2.7 | **UC-01 funnel echte funnel** — nu alleen daily-aggregaat per status; flow `INGEDIEND→IN_BEHANDELING→TOEGEKEND` mist | 🟠 | S |
| 7.2.8 | **UC-05 met SCD-2 + 30-dagen-window-metrics** | 🟡 | M |

### 7.3 Pipeline

| # | Item | Prio | Effort |
|---|---|---|---|
| 7.3.1 | **NiFi-flows daadwerkelijk implementeren** — nu placeholder; importeer JSON | 🟡 | L |
| 7.3.2 | **`spark-jobs/lakehouse_maintenance.py`** — maintenance-DAG verwijst nu naar Trino-procedures, maar voor production is een Spark-batch met statistics-update + manifest-rewrite-strategie beter | 🟡 | M |
| 7.3.3 | **dbt-runs in Airflow-DAG echt werkend krijgen** — `repo_url` Variable instructions in runbook, maar nooit getest | 🟠 | S |
| 7.3.4 | **dbt manifest-upload naar MinIO** als post-task in `dbt_run_per_domain.py` (nu vereist door `om_ingest_dbt`) | 🟠 | S |

---

## 8. BI / Visualisatie

| # | Item | Prio | Effort |
|---|---|---|---|
| 8.1 | **WIA Funnel-dashboard** als zip — DoD-anchor | 🟠 | M |
| 8.2 | **UC-06 Cost forecast-dashboard** met scenario-vergelijking | 🟠 | M |
| 8.3 | **UC-07 DQ-dashboard** met alerts | 🟠 | S |
| 8.4 | **Superset row-level security** bovenop OPA — extra zekerheid | 🟡 | M |
| 8.5 | **Superset OIDC role-mapping** — automatisch `data_steward` → Superset `Alpha`, `marketing_analyst` → `Gamma` | 🟠 | S |
| 8.6 | **Superset `extraCredentials.purpose` doorzetten** naar Trino — nu gebruikt Superset zijn eigen connection-credentials, OPA krijgt geen purpose | 🔴 | L |
| 8.7 | **Superset assets-bundle in repo** voor declaratieve dashboard-deploy via Superset CLI | 🟡 | M |

---

## 9. OpenMetadata

| # | Item | Prio | Effort |
|---|---|---|---|
| 9.1 | **Reverse Metadata aan zetten** — OM `Purpose limitation.*` tags terug schrijven naar Trino kolom-tags → OPA-feed | 🟠 | M |
| 9.2 | **Auto-classification AAN** — laat OM zelf BSN-patronen detecteren | 🟠 | S |
| 9.3 | **Custom properties voor `algoritmeregister_id`** in OM-config | 🟡 | S |
| 9.4 | **Data Lifecycle Manager (DLM)** met `retention period_jaren` | 🟠 | M |
| 9.5 | **Lineage-waarschuwing** — alarmeer als nieuwe gold-tabel geen lineage heeft naar bronze | 🟡 | S |
| 9.6 | **OM observability-pipelines** voor query-history-volume per gebruiker | 🟡 | M |

---

## 10. Architecture / Design

| # | Item | Prio | Effort |
|---|---|---|---|
| 10.1 | **GitOps met ArgoCD** — vervangt manuele `kubectl apply -k` | 🟠 | M |
| 10.2 | **Multi-tenant overlays** — als meerdere divisies dezelfde infra delen | 🟡 | XL |
| 10.3 | **API-gateway voor UC-10** — Kong/APISIX voor `Mijn Gegevensdiensten 2.0` | 🟡 | XL |
| 10.4 | **Apart Spark-cluster per workload-type** — production kan streaming/batch/ML scheiden | 🟡 | L |
| 10.5 | **Stackable Cockpit UI** voor operationeel beheer | 🟡 | S |
| 10.6 | **ADR-0007: kustomize vs Helm-only** | 🟡 | S |
| 10.7 | **ADR-0008: NiFi → Kafka → Spark vs alternative ingest-strategie** | 🟡 | S |
| 10.8 | **DTAP-overlays** — separate dev/test/acc/prod kustomize-overlays | 🟠 | L |

---

## 11. Dev Experience

| # | Item | Prio | Effort |
|---|---|---|---|
| 11.1 | **Pre-commit hooks** (`.pre-commit-config.yaml`) — yamllint, ruff, opa fmt, shellcheck | 🟠 | S |
| 11.2 | **Tilt of Skaffold** voor inner-loop development | 🟡 | M |
| 11.3 | **VSCode workspace settings** — Python + Rego + YAML + dbt extensions config | 🟡 | S |
| 11.4 | **`make rebuild-<component>`** shortcuts | 🟡 | S |
| 11.5 | **`doctor.sh` versie-pin-check** — niet alleen aanwezigheid, ook `kubectl >= 1.29` | 🟡 | S |
| 11.6 | **Smoke-tests parallel** — via GNU parallel of xargs | 🟡 | S |
| 11.7 | **`make logs <component>`** — kubectl-logs-helper | 🟡 | S |
| 11.8 | **dev-container (`.devcontainer/`)** — fully-configured VSCode/Codespaces dev-env | 🟡 | M |

---

## 12. Documentation

| # | Item | Prio | Effort |
|---|---|---|---|
| 12.1 | **Architecturediagram als image** (Mermaid in `docs/architecture.md` of PNG via draw.io) | 🟠 | S |
| 12.2 | **Project-glossary** in `docs/glossary.md` (afkortingen + UWV-specifieke begrippen) | 🟡 | S |
| 12.3 | **Data-flow-diagram** per UC (sequence-diagrams) | 🟡 | M |
| 12.4 | **Onboarding-doc** voor nieuwe engineers — "in 1 dag van clone tot eerste DAG-run" | 🟠 | M |
| 12.5 | **API-cookbook** — `curl`-voorbeelden voor Trino, OM, Superset REST-API | 🟡 | M |
| 12.6 | **Use-case-spec verdiepen** voor UC-08, UC-09, UC-10 (nu 1 pagina, production wil 5+ pagina's) | 🟡 | L |
| 12.7 | **CGM-glossary in `docs/`** parallel aan OM-glossary (offline-readable) | 🟡 | S |
| 12.8 | **Operationele runbooks per UC** in plaats van alleen platform-runbook | 🟡 | M |

---

## 13. Testing

| # | Item | Prio | Effort |
|---|---|---|---|
| 13.1 | **Unit-tests voor `spark-jobs/`** — pytest met PySpark fixtures | 🟠 | M |
| 13.2 | **Integration-tests** in `tests/integration/` — Trino-via-Java-client, Kafka-producer/consumer-roundtrip | 🟠 | M |
| 13.3 | **Load-tests** met k6 op Trino REST API | 🟡 | M |
| 13.4 | **Security-tests** — OWASP ZAP op Superset/Airflow UI | 🟡 | M |
| 13.5 | **Fast-e2e** (`tests/e2e/smoke-only.sh`) zonder bootstrap voor pull-request-CI | 🟠 | S |
| 13.6 | **Property-based tests** voor BSN-generator (hypothesis) | 🟡 | S |
| 13.7 | **OPA test-coverage > 80%** + opa-coverage in CI | 🟠 | S |
| 13.8 | **dbt-test-coverage** — welke kolommen hebben géén tests? | 🟡 | S |
| 13.9 | **Mutation testing** op Rego — genereert variants, kijkt of tests blijven falen | 🟡 | L |

---

## 14. CI/CD

| # | Item | Prio | Effort |
|---|---|---|---|
| 14.1 | **CI-pipeline lokaal draaien** — act of `make ci` | 🟡 | S |
| 14.2 | **Caching** in CI workflows (pip, helm-charts, k3d-images) | 🟡 | S |
| 14.3 | **Required-checks** op main-branch — protected branch + reviewers | 🟠 | S |
| 14.4 | **CD-pipeline naar dev-cluster** — auto-deploy bij merge | 🟠 | M |
| 14.5 | **Blue/green of canary** voor TrinoCluster updates | 🟡 | M |
| 14.6 | **Promotion-pipeline** dev → staging → prod met manual approval | 🟠 | M |
| 14.7 | **Image-mirror voor air-gapped CI** | 🟡 | M |
| 14.8 | **Renovate-bot** voor automatische dep-updates (zie ook §2.6.5) | 🟡 | S |

---

## 15. FinOps / Cost / Sustainability

| # | Item | Prio | Effort |
|---|---|---|---|
| 15.1 | **Cost-labels per pod** — `odap.io/cost-center: <divisie>` | 🟡 | S |
| 15.2 | **Kubecost / OpenCost** voor dev-zichtbaarheid | 🟡 | M |
| 15.3 | **Off-hours scaling-to-zero** met KEDA | 🟡 | M |
| 15.4 | **Spot/preemptible nodes** voor batch-workloads | 🟡 | L |
| 15.5 | **Kepler / Scaphandre** voor energie-meting | 🟡 | M |
| 15.6 | **Trino result-cache** verlaagt query-cost (zie ook §4.7) | 🟡 | M |

---

## 16. Internationalization / Accessibility

| # | Item | Prio | Effort |
|---|---|---|---|
| 16.1 | **README.en.md** voor non-Dutch contributors | 🟡 | M |
| 16.2 | **WCAG 2.2 AA-audit** op Superset — kleurcontrast, keyboard-nav | 🟡 | M |

---

## Prioritering: top-15 als quick-wins

Kort + hoog-rendement, in volgorde:

1. **§5.1 PrometheusRule alerts** (S, 🔴) — direct waardevol voor operationele zichtbaarheid
2. **§1.10 KafkaTopic CRDs** (S, 🟠) — ontwerp-schoonmaak; auto-create is technisch debt
3. **§1.4 PodDisruptionBudget + HPA** (S, 🟠) — voorkomt onnodige downtime
4. **§1.5 ResourceQuota / LimitRange** (S, 🟠) — voorkomt resource-noise tussen namespaces
5. **§5.9 Alertmanager met Slack** (S, 🟠) — alerts moeten ergens heen
6. **§2.3.1 MFA verplicht** (S, 🔴) — security-baseline
7. **§2.7.1 Pseudonymize-macro gebruiken** (M, 🔴) — UC-09 sandbox vraagt erom
8. **§11.1 Pre-commit hooks** (S, 🟠) — verlaagt CI-friction
9. **§6.4 Retention period-DAG** (M, 🔴) — AVG-verplichting
10. **§1.16 SECURITY.md** (S, 🟠) — NIS2 vulnerability disclosure
11. **§7.2.5 dbt-meta-block CI-check** (S, 🟠) — voorkomt regressie van compliance-meta
12. **§2.4.1 OPA decision-log naar OS** (M, 🔴) — audit-trail
13. **§8.1 WIA Funnel-dashboard** (M, 🟠) — DoD-anchor
14. **§13.5 Fast-e2e** (S, 🟠) — verlaagt CI-cyclus voor PRs
15. **§5.3 OpenSearch ILM** (S, 🟠) — voorkomt log-volume-explosie

---

## Wat NIET op deze lijst staat

- **Zaken die expliciet "out-of-scope referentie" zijn**: actuele wettelijke teksten, production-Hyperscaler-keuze, formele aanbestedingsdocumenten, ENSIA-audit, NEN 7510-certificering. Dat zijn organisatorische/juridische trajecten.
- **Niet-werkende items uit master-prompt-aanname** die we al goed verwerkten: smoketest-via-NiFi (we kozen Python-loader), Helm-only-deploy (we mixen kustomize), Iceberg-default (we draaien Delta — ADR-0006 dekt het).

---

## Hoe te gebruiken

1. **Sprint-planning**: pak 3–5 items per sprint, prefereer 🔴 boven 🟠 boven 🟡.
2. **PR-driven**: 1 item = 1 PR; link naar dit document met `Closes #improvements-§<x.y>`.
3. **Review-cyclus**: dit document zelf 6-maandelijks bijwerken na production-feedback.
4. **Acceptatie**: een item is "done" als (a) implementatie + tests + (b) docs/runbook bijgewerkt + (c) compliance-mapping evidence-pad bijgewerkt waar relevant.
