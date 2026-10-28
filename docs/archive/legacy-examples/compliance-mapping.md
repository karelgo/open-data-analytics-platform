# Compliance Mapping

Tabel met elke requirement uit
[`requirements.md`](../requirements.md)
gemapt op concrete maatregelen, fase waarin geleverd, en evidence (bestand of
setting). Status-kolom geeft fase 0-skeleton — `TBD` betekent "fase X levert
het bestand of de setting".

**Legend Fase**:
0 = repo & docs · 1 = cluster bootstrap · 2 = foundation services ·
3 = storage & query · 4 = ingestion · 5 = dbt & analytics · 6 = orchestratie ·
7 = BI · 8 = OpenMetadata · 9 = OPA-policies · 10 = compliance-evidence + e2e.

---

## SOC 2 — Architecture- en ontwerpprincipes

| R-* | Korte titel | Geleverd in | Evidence (path / setting) |
|---|---|---|---|
| R-NORA-01 | One-off vastleggen, meervoudig gebruiken | 8 | OM-services voor Trino + dbt + Superset + Airflow + Kafka in [`platform/13-openmetadata-config/services/`](../platform/13-openmetadata-config/services/); polisadm = single source of truth (UC-07) |
| R-NORA-02 | Open API's met versionering | 6, 10 | Trino REST API (Trino spec); OpenAPI spec voor toekomstige UC-10-gateway: zie [`docs/use-cases/uc10-gegevensdiensten.md`](use-cases/uc10-gegevensdiensten.md) (out-of-fase-10) |
| R-NORA-03 | Modulair en loosely coupled | 0, 1 | Stackable operators per component (12 SDP-CRDs); [ADR-0001](adr/0001-stackable-as-base.md) |
| R-NORA-04 | Open standaarden (Iceberg/Delta, Parquet, OAuth2/OIDC) | 0, 1, 3 | [`platform-config.yaml::table_format`](../platform-config.yaml), [ADR-0002](adr/0002-iceberg-vs-delta.md), Keycloak OIDC, Apache Iceberg + Delta Lake spec |
| R-NORA-05 | Vendor lock-in voorkomen | 0 | [ADR-0001](adr/0001-stackable-as-base.md), [ADR-0002](adr/0002-iceberg-vs-delta.md) (table-format-abstractie); alle components Apache 2.0 |
| R-NORA-06 | FAIR via data catalog | 8 | OpenMetadata services (auto-discovery) + [glossary-cgm.yaml](../platform/13-openmetadata-config/glossary-cgm.yaml) (22 termen) |
| R-NORA-07 | Transparant, proactief, herleidbaar | 8, 9 | OM lineage (Trino + dbt workflows); OPA decision-log naar OpenSearch via Vector |
| R-NORA-08 | Federatieve identity | 1 | [Keycloak realm](../infrastructure/helm/keycloak/realm.json) met 11 rollen + 7 OIDC-clients; [`AuthenticationClass keycloak`](../platform/02-authentication/authenticationclass-keycloak.yaml); **Entra ID brokering** via [`identityProviders[entra]`](../infrastructure/helm/keycloak/realm.json) — gebruiker kiest "lokaal platform account" of "Microsoft Entra ID" on the loginpagina; zie [ADR-0008](adr/0008-entra-broker-via-keycloak.md) |
| R-NORA-09 | Semantische interoperabiliteit | 8 | [OM glossary "CGM"](../platform/13-openmetadata-config/glossary-cgm.yaml) gekoppeld aan dbt-mart `meta.cgm_entiteiten` |

## AVG — Privacy & gegevensbescherming

| R-* | Korte titel | Geleverd in | Evidence |
|---|---|---|---|
| R-AVG-01 | Rechtsgrond per processing (art. 6/9) | 5, 9 | dbt `meta.legal_basis`; OPA-policy `trino-purpose-limitation.rego` |
| R-AVG-02 | Processingsregister (art. 30) | 8, 10 | OM Custom Properties op data products; export naar CSV |
| R-AVG-03 | DPIA voor hoog risico | 0, 5 | `docs/use-cases/uc02-complex-cases-ai.md` placeholder; UC-04, UC-09 |
| R-AVG-04 | Verwerkersovereenkomsten | n/a | Buiten platform-scope (organisatorisch) |
| R-AVG-05 | Dataminimalisatie (selectie als config) | 5, 9 | dbt-models projecteren expliciet; OPA column masks via `opa-policies-src/trino/trino-column-masks.rego` |
| R-AVG-06 | Purpose limitation per dataset | 5, 8, 9 | dbt `meta.purpose-limitation`; OM tag `Purpose limitation.*`; **`opa-policies-src/trino/trino-purpose-limitation.rego` + `data/role_mappings.json::resource_purposes`** (tests dekken DoD: data_steward zonder purpose op `gold.uc05_*` → deny) |
| R-AVG-07 | Pseudonimisering & anonimisering | 5, 9 | Macro `dbt/macros/pseudonymize.sql` (hash + zout); OPA column masks BSN/IBAN/diagnose in `opa-policies-src/trino/trino-column-masks.rego` |
| R-AVG-08 | Retention perioden | 5, 6, 11 | dbt `meta.retention period_jaren`; **`platform/11-airflow/dags/retention period_enforcer.py`** (daily DAG, dry-run-flag per tabel) |
| R-AVG-09 | Privacy by default (least privilege) | 9 | `opa-policies-src/trino/trino-base.rego::default allow := false` + role-list-restriction in `data/role_mappings.json` (alleen `claims_analyst` + `platform_admin` hebben `sensitive` catalog) |
| R-AVG-10 | Inzage/rectificatie/verwijdering | 5, 6 | `gdpr_request` DAG; dbt-models met `bsn` als unique key |
| R-AVG-11 | SAR over alle datalagen | 8 | OM lineage tabel-/kolom-niveau |
| R-AVG-12 | Geautomatiseerde besluitvorming (art. 22) | 0, 5 | `docs/use-cases/uc02-*` mens-in-de-lus design; UC-03 |
| R-AVG-13 | Doorgifte buiten EER | 0 | n.v.t. — alle storage in cluster, regio `eu-nl-1` (`platform-config.yaml`) |
| R-AVG-14 | Datalocatie configureerbaar | 0 | `platform-config.yaml` `region`-tag |
| R-AVG-15 | Datalek-detectie 72u | 1, 9, 10, 11 | [Vector](../infrastructure/helm/vector/values.yaml) audit-route → `logs-audit-*` (7-jaar [ILM](../platform/14-monitoring/opensearch-ilm-job.yaml)); [PrometheusRule alerts](../platform/14-monitoring/prometheusrule.yaml); meldplicht-procedure [runbook.md § 4](runbook.md#4-veelvoorkomende-incidenten) |

## ISO 27001 / ISO 27002 — Informatiebeveiliging

| R-* | Korte titel | Geleverd in | Evidence |
|---|---|---|---|
| R-BIO-01 | ISMS conform ISO 27001 | n/a | Buiten platform-scope (organisatorisch) |
| R-BIO-02 | Risicoanalyse met BIV-classificatie | 8 | OM Classification `BIO.BIV.*` per dataset |
| R-BIO-03 | Verklaring van Toepasselijkheid | n/a | Buiten platform-scope |
| R-BIO-04 | Periodieke audits | 10 | [`docs/runbook.md` § 10](runbook.md#10-compliance-evidence-verzamelen) — `make opa-test` (23/23) + OM-classifications-export |
| R-BIO-05 | Centraal IAM + MFA | 1, 11 | [Keycloak realm](../infrastructure/helm/keycloak/realm.json) **+ password-policy `length(12)+digits+upper+special+notUsername+history(5)` + sessie-timeouts + TOTP-policy + `requiredActions: CONFIGURE_TOTP` op admin-rollen** |
| R-BIO-06 | RBAC/ABAC + recertificering | 9 | `opa-policies-src/trino/trino-platform-roles.rego` + `data/role_mappings.json` (12 rollen × catalogs/schemas/purposes/capabilities). Recertificering buiten scope. |
| R-BIO-07 | Privileged Access Management | n/a | Buiten platform-scope (sessie-recording etc.) |
| R-BIO-08 | Service-accounts via secrets manager | 1, 2 | [Stackable secret-operator](../infrastructure/stackablectl/release.yaml) + cert-manager + [`platform/01-secrets/secretclasses.yaml`](../platform/01-secrets/secretclasses.yaml). Production: External Secrets Operator + Vault. |
| R-BIO-09 | Encryption at rest + TLS 1.2+ | 1, 2 | [MinIO TLS-config](../infrastructure/helm/minio/values.yaml); cert-manager `platform-issuer` voor alle `*.odap.local`; Stackable internal-mTLS via `tls-internal` SecretClass |
| R-BIO-10 | Sleutelbeheer (HSM/KMS, BYOK) | n/a | Buiten scope dev-cluster (production: KMS) |
| R-BIO-11 | Column-/row-level security + masking | 9 | `opa-policies-src/trino/trino-row-filters.rego` (regio-filter WIA, opt-out UC-04, sandbox-pseudo) + `trino-column-masks.rego` (BSN/IBAN/bankrekening/diagnose/birth_date per rol). Tests in `*_test.rego` (23/23 PASS). Smoke `tests/smoke/08-opa-decisions.sh`. |
| R-BIO-12 | Verplichte dataclassificatie | 4, 8 | [`classifications.yaml`](../platform/13-openmetadata-config/classifications.yaml) (7 categorieën, ~50 tags); dbt-models hebben `meta.bio_classificatie` (publiek/intern/vertrouwelijk/geheim) |
| R-BIO-13 | Netwerksegmentatie + zero-trust | 1, 2, 11 | Namespaces per zone + Pod-Security baseline + **[ResourceQuota + LimitRange](../platform/00-namespaces/resourcequota-limitrange.yaml)** per ns. NetworkPolicies (`TBD` production). |
| R-BIO-14 | Hardening + IaC + policy-as-code | 0, 1, 9 | Alle Stackable workloads via Helm/Kustomize; [OPA-bundle](../platform/10-opa/) voor data-laag policy-as-code |
| R-BIO-15 | Vulnerability management | 10 | CI scan met Trivy ([`ci/github-actions/security-scan.yml`](../ci/github-actions/security-scan.yml)) |
| R-BIO-16 | Endpoint protection | n/a | Buiten platform-scope |
| R-BIO-17 | Secure SDLC (SAST/DAST/SCA) | 10 | GitHub Actions ([`ci/github-actions/`](../ci/github-actions/)): `ruff`, `opa test`, `dbt parse`, yamllint, Trivy |
| R-BIO-18 | DTAP-scheiding + synthetische testdata | 0, 4 | [`data-generation/`](../data-generation/) — alleen 9-prefix test-BSN's, `meta.synthetic: true` op elk record. Aparte clusters per omgeving via Stackable-stack-files (TBD production). |
| R-BIO-19 | Change management + GitOps | 10 | GitHub Actions ([`ci/github-actions/`](../ci/github-actions/)); 6 ADRs in [`docs/adr/`](adr/); kustomize-driven deploys |
| R-BIO-20 | Centrale logging onveranderbaar (≥6 mnd) | 1, 8, 11 | [Vector](../infrastructure/helm/vector/values.yaml) audit-route → `logs-audit-*` met **[ILM 7-jaar](../platform/14-monitoring/opensearch-ilm-job.yaml)**; OPA decision-logs via `decision_logs.console: true` configOverride |
| R-BIO-21 | SIEM/SOC-integratie | n/a | OpenSearch index → externe SIEM-connector (out-of-cluster, production) |
| R-BIO-22 | Incident response plan | 10 | [`docs/runbook.md` § 4](runbook.md#4-veelvoorkomende-incidenten) — 5 scenario-runbooks |
| R-BIO-23 | Backup 3-2-1 + immutable | 10 | [`docs/runbook.md` § 5](runbook.md#5-backup-restore) — MinIO mirror, Postgres dumps, Keycloak realm-export. Production: MinIO Object Lock + replicatie. |
| R-BIO-24 | RTO/RPO + DR-tests | 10 | [`docs/runbook.md` § 5 + § 6](runbook.md#5-backup-restore) — dev RTO ≈ 30 min (re-deploy from scratch), RPO ≈ laatste seed |

## NIS2 — Cyberweerbaarheid

| R-* | Korte titel | Geleverd in | Evidence |
|---|---|---|---|
| R-NIS2-01 | Bestuurlijke verantwoordelijkheid | n/a | Organisatorisch |
| R-NIS2-02 | All-hazards risicomanagement | n/a | Organisatorisch |
| R-NIS2-03 | Supply chain security (SBOM) | 10 | Stackable images SBOM-verifieerbaar via `cosign verify --certificate-identity ... docker.stackable.tech/...` (CI-scan in [`ci/github-actions/security-scan.yml`](../ci/github-actions/security-scan.yml)) |
| R-NIS2-04 | Meldplicht 24/72u/1mnd | 10 | [`docs/runbook.md` § 4.5](runbook.md#4-veelvoorkomende-incidenten) — incident-detect via Prometheus + OpenSearch alert-rules (TBD production volledige uitwerking) |
| R-NIS2-05 | Vulnerability disclosure-beleid | 10, 11 | [`SECURITY.md`](../SECURITY.md) — SLA per CVSS-severity, in/out-of-scope, 90-dagen-default-disclosure |
| R-NIS2-06 | MFA voor kritieke systemen | 1, 11 | Keycloak realm — **TOTP-policy + `requiredActions: ["CONFIGURE_TOTP"]` op `platform.admin`, `data.engineer`, `case.manager`**; passkeys voor production via WebAuthn |
| R-NIS2-07 | Versleutelde communicatie | 1, 2 | cert-manager `platform-issuer` ClusterIssuer voor alle ingress; Stackable secret-operator + `tls-internal` SecretClass voor mTLS tussen pods |
| R-NIS2-08 | Awareness en training | n/a | Organisatorisch |
| R-NIS2-09 | Crisismanagement / BCM | 10 | [`docs/runbook.md` § 2 + § 5 + § 6](runbook.md#2-cluster-lifecycle); production: tabletop + technical exercise per kwartaal (organisatorisch) |
| R-NIS2-10 | Effectiviteitsmeting (KPI's) | n/a | Organisatorisch |

## Data governance, kwaliteit, metadata

| R-* | Korte titel | Geleverd in | Evidence |
|---|---|---|---|
| R-GOV-01 | Eigenaarschap per data product | 5, 8 | Elk dbt-model heeft `meta.eigenaar` (zie 16 schema.yml in [`dbt/models/`](../dbt/models/)); OM service-owner per ingestion-pipeline |
| R-GOV-02 | Catalog incl. classificatie/lineage/SLA | 8 | OM service-configs in [`platform/13-openmetadata-config/services/`](../platform/13-openmetadata-config/services/) + 7 classifications + CGM-glossary |
| R-GOV-03 | OpenLineage end-to-end | 8 | [`om_ingest_trino.py`](../platform/11-airflow/dags/om_ingest_trino.py) (lineage uit query-history); [`om_ingest_dbt.py`](../platform/11-airflow/dags/om_ingest_dbt.py) (lineage uit dbt manifest); Superset + Airflow services in OM |
| R-GOV-04 | Datakwaliteits-SLO's + tests | 5, 8 | dbt-tests in 16 schema.yml + 3 custom generic tests (`bsn_valid`, `iban_valid`, `lh_nummer_valid`) + 2 singular tests; OM Profiler op silver-schemas; [UC-07 dagrapport](../dbt/models/marts/uc07_dq_policies/) |
| R-GOV-05 | Master data management | 5 | [Mart UC-05 client_360](../dbt/models/marts/uc05_customer_360/mart_uc05_customer_360.sql) joint per BSN; CGM-seeds (claim payout_typen / wet_codes / regio_codes) |
| R-GOV-06 | Policy-as-code | 9 | OPA Rego bundle (5 policy-files + 4 test-files in `opa-policies-src/`); `make opa-test` (23/23 lokaal); `scripts/build-opa-bundle.sh` rendert ConfigMap; kustomize `configMapGenerator` met label `opa.stackable.tech/bundle: "true"` |
| R-GOV-07 | Data contracts | 5 | dbt schema.yml + tests; expliciete `meta` |

## Functioneel

| R-* | Korte titel | Geleverd in | Evidence |
|---|---|---|---|
| R-FUN-01 | Batch + micro-batch + streaming ingestion | 4 | [NiFiCluster](../platform/07-nifi/nificluster.yaml) (batch — fase 5+) + [Kafka](../platform/06-kafka/) + [Spark Structured Streaming](../platform/08-spark/apps/streaming-bronze.yaml) (micro-batch 20s) |
| R-FUN-02 | Schema-validatie + quarantine | 4, 5 | NiFi quarantine-flow (zie [`nifi-flows/templates/delta/README.md`](../nifi-flows/templates/delta/README.md)); dbt-tests in 16 schema.yml |
| R-FUN-03 | PII-detectie at ingest | 4, 8 | NiFi UpdateAttribute (fase 5+) + OM Auto-Classification + [classifications.yaml::PII](../platform/13-openmetadata-config/classifications.yaml) (9 PII-tags) |
| R-FUN-04 | Lakehouse-medallion + ACID | 3, 4 | Delta-tabellen op MinIO + 4 Trino-catalogs (bronze/silver/gold/sensitive) + Hive Metastore. [ADR-0006](adr/0006-delta-chosen-for-this-implementation.md). |
| R-FUN-05 | Compute/storage gescheiden | 0 | Stackable Trino (compute) + MinIO (storage) onafhankelijk schaalbaar; [ADR-0001](adr/0001-stackable-as-base.md) |
| R-FUN-06 | Time travel / versionering | 4, 6 | Delta `VERSION AS OF` + [`lakehouse_maintenance.py`](../platform/11-airflow/dags/lakehouse_maintenance.py) format-aware OPTIMIZE/VACUUM |
| R-FUN-07 | Self-service BI met semantische laag | 5, 7 | Superset + dbt-marts (16 datasets in [`dbt/models/marts/`](../dbt/models/marts/)) — semantische laag via dbt schema.yml `meta` |
| R-FUN-08 | MLOps (registry, feature store, monitoring) | 5 (placeholder) | [UC-02 spec](use-cases/uc02-complex-cases-ai.md) — placeholder; volledig MLOps in aparte repo |
| R-FUN-09 | Verklaarbaarheid + bias-toetsing | 5 (placeholder) | [UC-02 spec](use-cases/uc02-complex-cases-ai.md) (model-card + IAMA + bias-toets verplicht); [UC-03 spec](use-cases/uc03-fraud-risk.md) (`test_no_protected_attributes_uc03`) |
| R-FUN-10 | AI Act-aansluiting | 8 | OM Classification [`AI.Risk-{Laag,Midden,Hoog,Verboden}`](../platform/13-openmetadata-config/classifications.yaml) + `AI.HumanInTheLoop` + `AI.Algoritmeregister-Geregistreerd` |
| R-FUN-11 | API-management | 10 | [UC-10 spec](use-cases/uc10-gegevensdiensten.md); production-gateway uitwerking in MyGegevensdiensten 2.0 (out-of-scope referentie) |
| R-FUN-12 | Event-gedreven + schema registry + DLQ | 4, 11 | [KafkaCluster](../platform/06-kafka/kafkacluster.yaml) + **[declaratieve KafkaTopic-Job](../platform/06-kafka/kafkatopics-job.yaml)** met 14 topics (incl. `.dlq`-suffix per domein); `auto.create.topics.enable=false` |

## Niet-functioneel

| R-* | Korte titel | Geleverd in | Evidence |
|---|---|---|---|
| R-NF-01 | SLO + multi-AZ | n/a | Buiten dev-scope (production: 99.9% per dienst, multi-AZ via cloud-provider) |
| R-NF-02 | Schaalbaarheid | 0, 1 | Stackable `roleGroups[].replicas` (default scaled-down); production verhoogt brokers/coordinators/workers |
| R-NF-03 | Observability (metrics/logs/traces) | 1, 8 | [kube-prometheus-stack](../infrastructure/helm/prometheus-stack/values.yaml) + [Vector](../infrastructure/helm/vector/values.yaml) → OpenSearch + OpenTelemetry-ready |
| R-NF-04 | FinOps | n/a | Out-of-scope (production: cost-allocation per namespace + label `odap.io/cost-center`) |
| R-NF-05 | Duurzaamheid | n/a | Out-of-scope referentie (production: groene regio's + workload-scheduling) |
| R-NF-06 | WCAG 2.2 AA | 7 | Superset 4.1+ heeft basis-WCAG (kleurschema, keyboard-nav). Eindgebruiker-UI via Workspace (organisatorisch, out-of-scope referentie). |
| R-NF-07 | Documentation + ADRs + runbook | 0–10 | 6 ADRs in [`docs/adr/`](adr/); [runbook.md](runbook.md) (11 secties); READMEs per `platform/<onderdeel>/`; 10 use-case-specs in [`docs/use-cases/`](use-cases/) |

## Compliance / audit

| R-* | Korte titel | Geleverd in | Evidence |
|---|---|---|---|
| R-COMP-01 | GRC-mapping actueel | 0–10 | Dit document — werkt-in-uitvoering, bijgewerkt per fase ([WORKLOG.md](../WORKLOG.md)) |
| R-COMP-02 | Pentests / red-team | n/a | Organisatorisch (production: ≥1×/jaar via externe partij) |
| R-COMP-03 | Externe assurance (ISO/SOC2) | n/a | Organisatorisch — referentie levert technische bouwstenen |
| R-COMP-04 | DPIA/ISMS/risico onderhoud | 0, 5 | DPIA-placeholders in [UC-02](use-cases/uc02-complex-cases-ai.md) + [UC-04](use-cases/uc04-proactieve-tw.md) + [UC-09](use-cases/uc09-reintegration-effect.md); dbt-models met `meta.dpia_required: true` |
| R-COMP-05 | Toezichthouder-readiness | 10 | [`docs/runbook.md` § 10](runbook.md#10-compliance-evidence-verzamelen) — `make opa-test` + OM-classifications-export + dbt-test-resultaten als evidence-pakket |
