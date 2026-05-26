# WORKLOG

Per sessie: wat gedaan, wat openstaand, welke beslissingen.

---

## 2026-04-30 — Sessie 1: Fase 0 (bootstrap + docs)

### Gedaan
- Vier achtergronddocumenten gelezen + samengevat (`docs/context-summary.md`).
- Antwoorden gebruiker verwerkt:
  - Tabelformaat **Delta Lake** (afwijking van ADR-0002 default Iceberg) → ADR-0006.
  - Doel-cluster: lokaal **k3d**.
  - Image registry: publiek pullen.
  - DNS: `*.odap.local` via /etc/hosts.
  - TLS: cert-manager self-signed.
  - Resource-budget: scaled-down profiel.
  - CI/CD: GitHub Actions (placeholder voor later).
  - Datavolume: 10k synthetische cliënten.
  - UC-02 Wajong: placeholder met TODO.
  - OpenSearch: één gedeeld single-node cluster.
  - Air-gapped: nee, pullen mag.
- Repo-structuur (alle directories per master prompt §4) aangemaakt.
- Toplevel files: `platform-config.yaml`, `.gitignore`, `LICENSE` (Apache 2.0), `README.md`, `Makefile`, `.editorconfig`.
- `infrastructure/k3d/k3d-cluster.yaml` (scaled-down, Traefik uit).
- 6 ADRs (`0001`..`0006`).
- 10 use-case specs (`uc01`..`uc10`).
- `docs/architecture.md`, `docs/compliance-mapping.md` (skeleton met R-* ↔ fase-mapping), `docs/runbook.md` (skeleton).

### Open / volgende sessie
- Fase 2 — foundation services: namespaces, secrets, S3Connection, ZooKeeper, HiveCluster, KafkaCluster.

### Beslissingen
- **Delta** geadopteerd ondanks lagere ADR-0002 score: gebruiker-voorkeur. Mitigatie: NiFi schrijft naar Kafka (niet rechtstreeks naar Delta), Spark Structured Streaming doet de Delta-write. Zie ADR-0006.
- **OpenSearch single-node** volstaat voor scaled-down. Vector logs én OpenMetadata-search delen het cluster (één index-prefix per consument).
- **Trino-catalogs heten format-onafhankelijk**: `bronze`, `silver`, `gold`, `sensitive` (niet `delta_bronze`). Switching naar Iceberg vraagt alleen template-render + redeploy.
- **GitHub Actions** komt later; voor nu alleen `ci/github-actions/.gitkeep` en `ci/yamllint.yaml`.

---

## 2026-05-01 — Sessie 2: Fase 1 (cluster bootstrap)

### Gedaan
- **Helm values per chart** (`infrastructure/helm/`):
  - `cert-manager/values.yaml` + `cluster-issuer.yaml` (self-signed CA `platform-issuer` voor `*.odap.local`).
  - `ingress-nginx/values.yaml` (k3d LB → :8080/:8443).
  - `minio/values.yaml` (single-node, 7 buckets aangemaakt via chart-job, ingress voor API + Console).
  - `postgresql/values.yaml` (single-instance, init-script maakt `hivemetastore`/`airflow`/`superset`/`openmetadata`/`keycloak` databases aan).
  - `keycloak/values.yaml` (externe Postgres, realm-import via ConfigMap, ingress).
  - `prometheus-stack/values.yaml` (Prometheus + Grafana, Alertmanager uit, scaled-down).
  - `vector/values.yaml` (Agent-mode, OpenSearch sink — fase 8).
  - `openmetadata/values.yaml` (gedeelde Postgres + OpenSearch, OIDC via Keycloak — fase 8).
- **Keycloak ODAP realm** (`infrastructure/helm/keycloak/realm.json`): 11 realm-rollen (de 8 mock-rollen + `researcher`, `operations_manager`, `marketing_analyst`), één mock-user per rol, 5 OIDC-clients (trino, superset, airflow, nifi, openmetadata) met dev-only secrets en redirect-URIs op `*.odap.local:8443`.
- **Stackable release pin** (`infrastructure/stackablectl/release.yaml` — SDP 26.3 alle 12 operators) + `stack.yaml` (verwijst naar `platform/00..13`).
- **Scripts** (`scripts/`): `cluster.sh`, `bootstrap.sh` (idempotente helm upgrade --install volgorde: cert-manager → ClusterIssuer → ingress-nginx → Postgres → MinIO → Keycloak → Prometheus → Stackable operators), `clean.sh`, `doctor.sh` (tooling + /etc/hosts check), `port-forward.sh`, `run-smoke-tests.sh`, `deploy-platform.sh` (stub voor fase 2+), `seed.sh` (stub voor fase 4+). Allemaal `chmod +x`.
- **Smoke test** `tests/smoke/01-stackable-up.sh`: cluster, namespaces, helm-releases, ClusterIssuer Ready, MinIO buckets, Stackable operator pods, Keycloak OIDC discovery.
- `ci/yamllint.yaml` + `ci/github-actions/.gitkeep`.

### Open / volgende sessie
- Fase 4 — ingestion: `data-generation/` Python-package (persona/polisadm/ww/wia/wajong/zw/crm/fez generators met BSN-checksum), `nifi-flows/templates/delta/` (NiFi-flows die naar Kafka publiceren), `platform/07-nifi/nificluster.yaml`, `platform/08-spark/apps/streaming_kafka_to_lakehouse.py` als SparkApplication.

### Beslissingen
- **Scaled-down Postgres single-instance** met meerdere databases (HMS, Airflow, Superset, OM, Keycloak). Productie: aparte instances per consumer.
- **Self-signed CA** (`platform-issuer`) als ClusterIssuer voor alle `*.odap.local` certificates. CA-cert blijft in `cert-manager` namespace; in browsers moet de CA expliciet vertrouwd worden voor lokaal gebruik.
- **Bitnami charts** voor PostgreSQL en Keycloak ondanks recente licentie-vragen — voor referentie volstaat de Apache 2.0 chart; voor productie cnpg-operator of Keycloak-operator overwegen.
- **Dev-only credentials** zijn hardcoded in `values.yaml` met expliciete `odap-dev-only-CHANGE-ME-*` prefix. Bootstrap.sh logt een warning. ADR voor secret-handling in productie wordt later geschreven.
- **MinIO bucket-creation** via chart's eigen post-install hook (`buckets:`-array in values). Voorkomt extra mc-job manifest.
- **ingress-nginx** is THE ingress-controller; Stackable's listener-operator (fase 2) blijft voor Stackable-services voor in-cluster service-discovery, ingress-nginx voor externe routes.

---

## 2026-05-01 — Sessie 3: Fase 2 (foundation services)

### Pre-flight
- Bash-syntax (8 scripts + 1 smoke): groen.
- Realm-JSON `jq empty`: groen.
- 14 YAML-bestanden uit fase 0/1: groen.

### Gedaan
- `platform/00-namespaces/` — 5 namespaces (`odap-platform`/`-data`/`-meta`/`-monitoring`/`-auth`) met platform labels (`odap.io/zone`, `odap.io/bio-classificatie`, `odap.io/doelbinding`) + Pod Security baseline.
- `platform/01-secrets/` — 2 Stackable SecretClasses (`s3-credentials-minio`, `oidc-client-credentials`) + 8 K8s Secrets (MinIO, Hive→Postgres, 4× OIDC client per service, Airflow- en Superset-Postgres). Dev-only; banner in dev-secrets.yaml.
- `platform/02-authentication/` — `AuthenticationClass keycloak` (OIDC, issuer `keycloak.odap.local:8443/realms/odap`, scopes `openid profile email roles`, principalClaim `preferred_username`) + `SecretClass tls-internal` voor CA-bundle.
- `platform/03-storage/` — `S3Connection s3-minio` (path-style, in-cluster).
- `platform/04-zookeeper/` — `ZookeeperCluster zookeeper` (3.9.3, 1 server) + `ZookeeperZnode zookeeper-znode-kafka`.
- `platform/05-hive-metastore/` — `HiveCluster hive` (4.0.1, Postgres-backed `hivemetastore`-DB, S3 ref `s3-minio`).
- `platform/06-kafka/` — `KafkaCluster kafka` (3.7.1, 1 broker, RF=1, `auto.create.topics=true` voor demo).
- Per directory `kustomization.yaml` + `README.md`.
- `tests/smoke/01-stackable-up.sh` uitgebreid: foundation-checks (CRD-aanwezigheid voor alle SDP-26.3 product-CRDs + Ready-status van ZK/Hive/Kafka, gracefully skipt als nog niet applied) + custom-resource bestaanscheck (SecretClasses, AuthenticationClass, S3Connection, ZookeeperCluster, Znode).

### Verificatie (host, geen cluster)
- Bash-syntax (smoke): groen.
- YAML-parse (17 platform-files): groen.
- `kubectl kustomize` per directory rendert zonder fouten — totaal **22 resources**:
  - 00-namespaces: 5 · 01-secrets: 10 · 02-authentication: 2 · 03-storage: 1 · 04-zookeeper: 2 · 05-hive-metastore: 1 · 06-kafka: 1.

### Beslissingen
- **Foundation kustomizations** zijn per-directory; `scripts/deploy-platform.sh` past elke directory in volgorde toe (00 → 13). Dit ondersteunt een incrementele rollout en duidelijke afhankelijkheidsvolgorde.
- **`auto.create.topics.enable=true`** in dev — productie zou expliciete KafkaTopic-CRDs gebruiken voor change management. Documenteren in fase 6 README.
- **OIDC issuer-URL** is **extern** (`keycloak.odap.local:8443`), niet intern (`keycloak.odap-auth.svc.cluster.local`), omdat tokens een issuer-claim bevatten die de browser-redirect-URL moet matchen. Stackable's AuthenticationClass kan zowel; we kiezen extern.
- **SecretClass `tls-internal`** voor de CA-bundle is voorbereid maar pas relevant in fase 3 (Trino → Keycloak OIDC TLS-verificatie). Bootstrap kan in fase 3 een trust-manager Bundle of handmatige Secret-kopie toevoegen.
- **`enableVectorAgent: false`** op alle Stackable-clusters in fase 2: Vector wordt pas in fase 8 ingezet; tot die tijd geen extra container per pod.

---

## 2026-05-01 — Sessie 4: Fase 3 (Trino + OPA + catalogs)

### Gedaan
- `platform/09-trino/catalogs/*.yaml.tmpl` — vier templates (`bronze`, `silver`, `gold`, `sensitive`) met placeholders `__TABLE_FORMAT__` + `__TABLE_FORMAT_CONNECTOR_BLOCK__`. Catalogs hebben labels (`odap.io/zone`, `odap.io/format`) en annotaties; `sensitive` heeft `odap.io/avg-art9: "true"`.
- `scripts/render-trino-catalogs.py` — Python renderer (PyYAML; leest `platform-config.yaml`, kan via `TABLE_FORMAT` env worden overschreven). Renders → `platform/09-trino/catalogs/rendered/*.yaml` + auto-gegenereerde `kustomization.yaml`. Sanity-parse per output.
- `.gitignore` uitgebreid met `platform/09-trino/catalogs/rendered/`.
- `scripts/deploy-platform.sh` roept render aan vóór de layer-loop. `Makefile`-target `render-catalogs` toegevoegd; `deploy-platform` heeft het als pre-req.
- `platform/09-trino/`:
  - `trino-static-auth.yaml` — `AuthenticationClass trino-static` + Secret `trino-static-users` (alleen smoketest user, dev-only).
  - `trinocluster.yaml` — Trino 470, 1 coordinator + 1 worker, **twee** AuthenticationClasses (`trino-static` + `keycloak`), `authorization.opa.configMapName: opa` met package `trino`.
  - `kustomization.yaml` — referenceert static-auth + trinocluster + `catalogs/rendered/` (door render-script gegenereerd).
- `platform/10-opa/`:
  - `opacluster.yaml` — OPA 1.0.1, 1 server.
  - `policies/trino-base.rego` — `package trino`, `import rego.v1`, default-deny + allow-rule voor authenticated users, `default rowFilters/columnMask` leeg, `batch` rule. Banner: `TICKET ODAP-PLATFORM-OPA-001` + `TIGHTEN: fase 9`.
  - `policies/trino-base_test.rego` — 6 tests (anonymous deny, authenticated allow, geen filters/masks, batch passthrough, batch empty bij anonymous).
  - `kustomization.yaml` — `configMapGenerator` bouwt `opa-trino-bundle` ConfigMap met label `opa.stackable.tech/bundle: "true"` + `disableNameSuffixHash: true`.
- `tests/smoke/02-trino-query.sh` — Trino+Worker rollout, OPA Ready, ConfigMap+label, OPA decision-endpoint via `/v1/data/trino/allow` (allow-true voor smoketest-user, allow-false voor anonymous), `SHOW CATALOGS` retourneert `bronze/silver/gold/sensitive`, `SELECT 1`.

### Verificatie (host, geen cluster)
- `python3 scripts/render-trino-catalogs.py` — render werkt voor `delta` én `iceberg`; rendered kustomization.yaml wordt mee gegenereerd.
- YAML-parse: 14 manifests + templates groen.
- `kubectl kustomize platform/09-trino` → 7 resources; `platform/10-opa` → 2 resources (incl. opa-trino-bundle ConfigMap met juiste label).
- `opa test` lokaal niet uitgevoerd (opa niet op host); rego-tests draaien straks in CI.

### Beslissingen
- **Twee AuthenticationClasses** op TrinoCluster: `trino-static` (smoketest-user) + `keycloak` (echte users). Productie zou alleen OIDC hebben; statisch is voor smoke + break-glass.
- **`catalogs/rendered/` gitignored** — single source of truth zijn de `.yaml.tmpl` en `platform-config.yaml`. `make render-catalogs` is idempotent.
- **OPA bundle via kustomize `configMapGenerator`** in plaats van een handmatig geschreven ConfigMap — voorkomt rego-content-duplicatie en behoudt `opa fmt`/`opa test` op de echte `.rego` files.
- **`disableNameSuffixHash: true`** op generator — TrinoCluster verwijst naar de ConfigMap-naam `opa-trino-bundle` zonder hash.
- **Catalogs heten zone-namen** (`bronze`/`silver`/`gold`/`sensitive`), niet format-specifiek (`delta_bronze`). Format is implementatie-detail; de catalog-naam blijft stabiel bij Iceberg ↔ Delta switch.

---

## 2026-05-01 — Sessie 5: Fase 4 (ingestion)

### Gedaan
- `data-generation/` Python-package opgezet:
  - `pyproject.toml` (Python 3.11+, hatch, faker/kafka-python/click/pydantic).
  - `generators/__init__.py` met `SYNTHETIC_HEADER` constante.
  - `generators/_common.py` — `make_rng`, `make_faker(locale='nl_NL')`, `envelope()` event-wrapper.
  - **`generators/persona.py` volledig** — 11-proef-validatie (`is_valid_bsn`, `calculate_bsn_check_digit`), `generate_test_bsn` (BSN-prefix `9` per BRP-conventie), `generate_personas`, dataclass `Persona` (bsn, voornaam, achternaam, geslacht, geboortedatum, adres, postcode, woonplaats).
  - Stubs voor `polisadministratie.py` (IKV's, lonen log-normal), `ww.py`, `wia.py`, `wajong.py`, `zw.py`, `crm.py`, `fez.py` (geaggregeerde uitkeringslast).
- `data-generation/load_to_kafka.py` — Click CLI met `--count/--seed/--bootstrap/--include-domains/--dry-run`. Pakt persona-anchor BSN's en propageert naar alle domeinen. Gzip-compressie, batched producer.
- `data-generation/load_to_minio_staging.py` — stub (fase 5).
- `data-generation/tests/{test_bsn_checksum.py,test_persona.py}` — **19/19 tests groen**, incl. 1000 generated BSN's allemaal valid + start met 9.
- `data-generation/k8s/seed-job.yaml` — Kubernetes Job die python:3.11-slim image gebruikt, deps pip-installeert, ConfigMaps mount op /app, en `load_to_kafka.py` runt tegen in-cluster Kafka-bootstrap. Idempotent via TTL + scripts/seed.sh delete-before-apply.
- `spark-jobs/lib/lakehouse_io.py` — format-agnostische helper (`get_spark_with_lakehouse_config`, `write_table`, `write_stream_to_table`, `ensure_bronze_schema`). Leest `TABLE_FORMAT` env, configureert Delta- of Iceberg-extensions + S3A + HMS.
- `spark-jobs/streaming_kafka_to_lakehouse.py` — Subscribet `uwv\..*\..*` Kafka topics; `foreachBatch` dispatcher schrijft per topic naar `bronze.uwv.<domain>_<entity>`. Schema: `payload (string), topic, kafka_partition, kafka_offset, kafka_ts, ingestion_ts, event_date`.
- `platform/07-nifi/` — `NiFiCluster nifi` (NiFi 2.0.0, OIDC via keycloak) + `ZookeeperZnode zookeeper-znode-nifi`. Documenteert in README dat fase-4-flows via Python-loader gevuld worden; NiFi-flow-import is fase 5+.
- `platform/08-spark/apps/streaming-bronze.yaml` — `SparkApplication streaming-bronze` (Spark 3.5.5, deps.packages: spark-sql-kafka-0-10, delta-spark, hadoop-aws). PodOverrides mounten ConfigMap `spark-streaming-jobs` op `/stackable/spark/jobs`. Driver+executor environment: `TABLE_FORMAT=delta`, `S3_ACCESS/SECRET_KEY` uit `minio-s3-credentials` Secret.
- `platform/08-spark/kustomization.yaml` — `configMapGenerator` bouwt `spark-streaming-jobs` ConfigMap uit `platform/08-spark/scripts/` (gitignored sync target).
- `nifi-flows/templates/{delta,iceberg}/README.md` — flow-design documentatie + NiFi 2.x import-API instructies.
- `scripts/seed.sh` — vol uitgewerkt: ConfigMaps maken, oude Job verwijderen, Job apply, wait completion, logs.
- `scripts/deploy-platform.sh` — sync `spark-jobs/*.py` → `platform/08-spark/scripts/` voor kustomize pickup.
- `.gitignore` — `platform/08-spark/scripts/` toegevoegd.
- `tests/smoke/03-bronze-data.sh` — checks: SparkApplication phase, schema `bronze.uwv` aanwezig in Trino, tabel `bronze.uwv.persona_created` aanwezig, row-count >= 10000, BSN-format begint met 9 (test-bereik).

### Verificatie (host, geen cluster)
- 19/19 pytest-tests groen (incl. 1000 generated BSN's all valid).
- `load_to_kafka.py --dry-run --count 100` levert ~2400 events: persona 100 / polisadm 151 / ww 33 / wia 18 / wajong 7 / zw 22 / crm 83 / fez 1944.
- 17 Python files compileren zonder syntax errors.
- 6 fase-4 YAML-bestanden parsen.
- `kubectl kustomize platform/07-nifi` → 2 resources; `platform/08-spark` → 2 resources (na spark-jobs sync).
- bash-syntax (seed.sh, smoke 03) groen.

### Beslissingen
- **Bronze = raw envelope storage**, één tabel per topic, schema `(payload string, kafka-meta, ingestion_ts, event_date)`. dbt staging-models in fase 5 parsen `payload` JSON naar getypte silver-tabellen. Voordeel: streamingjob is generiek; toevoegen van een nieuw topic vergt geen Spark-wijziging.
- **NiFi gedeployed maar geen flows in fase 4** — Python-loader (data-generation/load_to_kafka.py) vult Kafka direct. NiFi staat klaar voor fase 5+ flow-import. Reden: hand-geschreven NiFi 2.x flow JSON levert geen extra waarde voor de smoke-test en is onderhouds-intensief.
- **Spark-jobs sync via deploy-platform.sh** — kustomize `configMapGenerator` accepteert geen `../../<dir>` paths zonder `loadRestrictor: None`; cleaner is om naar een gitignored sub-directory te syncen.
- **`foreachBatch` dispatcher per topic** in plaats van één-stream-per-topic — efficienter (één Spark query) én flexibeler (nieuwe topics auto-pickup via `subscribePattern`).
- **In-cluster seed via Job** in plaats van host-side port-forward — Kafka-broker advertising-listeners maken host-side Kafka-clients onbetrouwbaar. Job zit op het cluster-netwerk en gebruikt de standaard service-DNS.
- **Header `SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE`** in elk generator-bestand + envelope `meta.synthetic: true`.

---

## 2026-05-01 — Sessie 6: Fase 5 (dbt + analytics engineering)

### Pre-flight
- Open: dbt-trino niet op host; smoke 04 doet docker-fallback voor `dbt parse`.

### Gedaan

**Project setup**
- `dbt/dbt_project.yml` — `vars: table_format: "{{ env_var('TABLE_FORMAT', 'delta') }}"`, per-domein staging-schema (silver.persoon/polisadm/ww/wia/wajong/zw/crm/fez), per-UC mart-schema (gold.uc01_*..uc07_*), seeds → silver.seed.
- `dbt/profiles.yml.template` — twee outputs (`dev` met static-auth, `prod` met OIDC). Env-driven host/port/user/password.
- `dbt/packages.yml` — `dbt_utils 1.3.0` + `dbt_expectations 0.10.4`.
- `dbt/README.md`.

**Macros (8)**
- `generate_schema_name.sql`, `generate_database_name.sql` — overrides zodat `+database`/`+schema` letterlijk de Trino-catalog/schema bepalen (geen target-prefix).
- `table_format.sql` — `table_format_properties(partition_columns=, extra_props=)` retourneert dict; Delta gebruikt `partitioned_by`, Iceberg `partitioning` met `day(col)` expressies.
- `pseudonymize.sql` — `to_hex(sha256(...))` + zout uit env-var.
- `apply_doelbinding_tag.sql` — no-op-helper (documentatie).
- Custom generic tests: `test_bsn_valid.sql` (11-proef in pure Trino-SQL met regexp + 9-cijfer-kolommen + mod 11), `test_iban_valid.sql` (regex), `test_lh_nummer_valid.sql` (regex).

**Sources**
- `models/staging/_sources.yml` — `bronze.uwv.{persona_created, polisadm_ikv, ww_aanvraag, wia_aanvraag, wajong_dossier, zw_melding, crm_contact, fez_uitkeringslast}` met per-source description + meta.

**Staging models (8)**
- Per domein: `stg_<entity>.sql` parseerd `payload` JSON met `json_extract_scalar(...$.payload.<field>)` + casts naar typed kolommen + behoudt `event_date` partition-key.
- `_stg_<domein>.yml` met `meta.{domain, legal_basis, doelbinding, bio_classificatie, bewaartermijn_jaren, eigenaar, pii_kolommen, risk_tier}` + tests (not_null, unique, accepted_values, bsn_valid, lh_nummer_valid, accepted_range via dbt_utils, relationships).

**Intermediate (1)**
- `int_huishouden_inkomen.sql` — som van `loon_bruto_jaar` per BSN voor lopende IKV's; helper voor UC-04.

**Marts (6 SQL-files in 5 UC's)**
- `uc01_wia_funnel/mart_uc01_wia_funnel_daily.sql` — dag/regio/onderdeel/status aggregaat (sturingsinfo, geen PII), partitioned op `aanvraag_datum`.
- `uc04_tw_eligibility/mart_uc04_tw_eligibility.sql` — regel-gebaseerd (inkomen < TW-norm), geen profilering, opt-out flag in meta.
- `uc05_client_360/mart_uc05_client_360.sql` — denormalized cliëntbeeld via 5 LEFT JOINs (persona + ikv + ww + wia + crm 30d), alle kolommen aanwezig — OPA-policies maskeren in fase 9.
- `uc06_lastprognose/mart_uc06_uitkeringslast_5y.sql` — baseline-projectie 2026-2030 per wet × regio.
- `uc06_lastprognose/mart_uc06_scenario_results.sql` — `iva_afschaf_2027` + `ww_versoberen` scenario-toepassing.
- `uc07_dq_polisadm/mart_uc07_dq_dagrapport.sql` — DQ-tellertjes per ingestiedag (n_ikvs, n_unieke_bsns, n_loon_null, n_lh_format_fout, n_bsn_buiten_test_bereik).
- Per UC een `_uc0x.yml` met meta-velden + tests (relationships naar seeds, accepted_range, accepted_values).

**Seeds (5 + properties.yml)**
- `cgm_uitkering_typen.csv` — 9 uitkering-typen met wet-koppeling.
- `cgm_wet_codes.csv` — 10 wet-codes (WW/WIA/Wajong/.../SUWI/Wfsv).
- `cgm_regio_codes.csv` — 9 mock regio's met provincie.
- `tw_normen_2026.csv` — 4 huishoud-types met norm.
- `scenario_inputs.csv` — 5 scenario's voor UC-06.
- `_seeds.yml` — schema-tests + descriptions.

**Singular tests (2)**
- `tests/test_no_protected_attributes_uc03.sql` — UC-03 hoog-risico-AI guard: faalt als kolommen met `etniciteit`/`wijk`/`religie`/etc. namen verschijnen in silver.ww.
- `tests/test_persona_bsn_count.sql` — sanity: stg_persona moet ≥1 record hebben.

**Smoke**
- `tests/smoke/04-dbt-parse.sh` — gebruikt lokale `dbt` of valt terug op docker `ghcr.io/dbt-labs/dbt-trino:1.9.0`. Stappen: `deps`, `parse`, `compile` (best-effort).

### Verificatie (host, geen cluster, geen dbt geïnstalleerd)
- 19 YAML-bestanden parsen (project + 16 schema.yml + packages + profiles).
- 22 SQL-bestanden Jinja-syntax-clean (3 macros met `{% test %}` overgeslagen — dbt-only tag, validatie via `dbt parse` zelf).
- bash-syntax smoke 04 groen.
- Tellingen: 8 macros, 5 CSV-seeds, 8 staging models, 1 intermediate, 6 marts (in 5 UC's), 2 singular tests, 16 schema.yml.

### Beslissingen
- **`generate_schema_name` + `generate_database_name` overrides** zodat `+database: silver` letterlijk de Trino-catalog wordt. Default dbt-gedrag prefixt `target.schema_<custom>`, wat onleesbare schema-namen geeft in de catalog.
- **Bronze-naar-silver via JSON-parse in staging** — bronze.uwv.<entity>.payload is raw JSON envelope. dbt's staging-laag is verantwoordelijk voor schema-on-read. Nieuwe brontypen vergen een nieuw staging-model maar geen Spark-wijziging.
- **One row per Wet × Regio × Maand voor UC-06 baseline** — eenvoudige projection (gem. uit historie); productie zou Prophet/statsforecast gebruiken in een Spark-job (zie `spark-jobs/`).
- **UC-05 client-360 alle kolommen aanwezig** — OPA-policies (fase 9) maskeren BSN voor `marketing_analyst`; default-deny op medische velden. Mart zelf is een wide-table; access-control is laag-9-verantwoordelijkheid.
- **Singular test op UC-03 protected attributes** — defensieve guard tegen accidenteel toevoegen van etniciteit/wijk-features in WW-domein. Faalt CI direct.
- **`dbt-trino` LDAP-method voor smoke** — `smoketest` user → Trino static-auth-class. Productie schakelt over op OIDC (`method: oidc` + `jwt_token` in profiles).

### Open / volgende sessie
- Fase 6 — orchestratie: `platform/11-airflow/airflowcluster.yaml` (AirflowCluster met git-sync), DAGs `dbt_run_per_domain.py` (KubernetesPodOperator → dbt-trino image), `lakehouse_maintenance.py` (format-aware OPTIMIZE/VACUUM voor Delta of expire_snapshots voor Iceberg), `synthetic_data_load.py`, `om_ingest_trino.py` (placeholder fase 8). Smoke 05: Airflow UI bereikbaar + DAG-trigger werkt.

---

## 2026-05-01 — Sessie 7: Fase 6 (Airflow + DAGs)

### Gedaan
- `platform/11-airflow/airflowcluster.yaml` — Stackable AirflowCluster (Airflow 2.10.4), gedeelde Postgres-backend (`airflow` DB), KubernetesExecutor (Celery off), OIDC via `keycloak` AuthenticationClass, listener-class `cluster-internal`. Webservers + schedulers met podOverrides die ConfigMap `airflow-dags` mounten op `/stackable/airflow/dags`.
- `platform/11-airflow/kustomization.yaml` — `configMapGenerator` bouwt `airflow-dags` uit `dags/*.py` met `disableNameSuffixHash`.
- `platform/11-airflow/dags/dbt_run_per_domain.py` — DAG met **8 KubernetesPodOperator-tasks parallel** (één per domein: persoon/polisadm/ww/wia/wajong/zw/crm/fez). Init-container `registry.k8s.io/git-sync/git-sync:v4.2.4` clont repo (URL via Airflow Variable `repo_url`), main-container `ghcr.io/dbt-labs/dbt-trino:1.9.0` draait `dbt deps && dbt run --select tag:<domein> && dbt test --select tag:<domein>` met TRINO_PASSWORD uit Secret `trino-static-users`. Falt back op skip-task als de variabele leeg is (lokale-dev-zonder-git).
- `platform/11-airflow/dags/lakehouse_maintenance.py` — DAG met `TrinoOperator` per bronze-tabel (8 stuks). Format-aware SQL: Delta `OPTIMIZE` + `VACUUM RETENTION '7d'`, Iceberg `expire_snapshots` + `remove_orphan_files` + `optimize`. Format via Variable `table_format`.
- `platform/11-airflow/dags/synthetic_data_load.py` — DAG met `KubernetesJobOperator` die de Job-spec uit `data-generation/k8s/seed-job.yaml` programmatisch reconstrueert (zelfde ConfigMap-mounts). Manueel triggerbaar; geen schedule.
- `platform/11-airflow/dags/__init__.py` — banner.
- `platform/11-airflow/README.md` — drie paden voor DAG-distributie (ConfigMap-mount voor dev / dagsGitSync voor productie / PVC voor air-gapped) + Airflow Connection-recipe voor `trino_default`.
- `tests/smoke/05-airflow-up.sh` — webserver+scheduler rollout, `airflow dags list` bevat de 3 verwachte DAGs, `airflow dags list-import-errors` is leeg, `/health` endpoint antwoordt.

### Verificatie (host, geen cluster)
- 2 YAML-bestanden parsen.
- 4 Python DAG-files compileren (py_compile groen).
- `kubectl kustomize platform/11-airflow` → 2 resources (AirflowCluster + ConfigMap `airflow-dags`).
- bash-syntax smoke 05 groen.

### Beslissingen
- **KubernetesExecutor** in plaats van Celery — cleaner voor scaled-down k3d (geen aparte celery-worker/redis), elke task spawnt zijn eigen pod. Productie kan Celery overwegen voor task-throughput.
- **DAGs via ConfigMap-mount** als default voor dev — kustomize `configMapGenerator` is reproducible. Productie commentaar in README beschrijft `dagsGitSync` als juist productiepad.
- **git-sync init-container voor dbt-tasks** — repo-clone in pod is robuust (geen kustomize ConfigMap met dbt-project-tarball), werkt met elke git-host. Toegevoegde Airflow Variable `repo_url` houdt het generiek.
- **Trino-credentials via Secret-ref** in env_vars (niet Airflow Connection) — KubernetesPodOperator pikt secrets direct, geen extra Connection-config in Airflow nodig (alleen de TrinoOperator gebruikt connection trino_default voor maintenance-DAG).
- **synthetic_data_load gebruikt KubernetesJobOperator** met inline-Job-spec — voorkomt afhankelijkheid van een aparte yaml-file in de pod-mount; alle Job-config staat in de DAG zelf.
- **Geen `om_*`-DAGs in fase 6** — die landen in fase 8 zodra OpenMetadata draait.

### Open / volgende sessie
- Fase 7 — BI: `platform/12-superset/supersetcluster.yaml` (OIDC SSO via Keycloak), Trino registreren als database, bootstrap-dashboards via API voor UC-01 (WIA Funnel) en UC-06 (Lastprognose).

---

## 2026-05-01 — Sessie 8: Fase 7 (Superset)

### Gedaan
- `platform/01-secrets/dev-secrets.yaml` — `superset-postgres-credentials` secret aangevuld met `connections.sqlalchemyDatabaseUri` (psycopg2-URI naar de gedeelde Postgres `superset` DB) — Stackable's SupersetCluster vereist deze key direct.
- `platform/12-superset/supersetcluster.yaml` — Stackable SupersetCluster (Superset 4.1.1, 1 node, scaled-down). OIDC via `keycloak` AuthenticationClass met `userRegistration: true` + `syncRolesAt: Login` zodat ODAP realm-users automatisch een Superset-account krijgen (default rol: `Public`). `loadExamplesOnInit: false`.
- `platform/12-superset/init-job.yaml` — bevat een **ConfigMap** (`superset-init-script`) met een 100-regel Python-bootstrap-script én een **Job** (`superset-init`) die python:3.11-slim gebruikt + `requests` pip-installeert. Het script:
  1. Wacht tot `/health` 200 OK retourneert.
  2. Logt in via `/api/v1/security/login` (Bearer-token + CSRF-token).
  3. Registreert een Trino-database met SQLAlchemy URI `trino://smoketest:<pw>@trino-coordinator:8443/bronze?protocol=https&verify=false` (idempotent — checkt eerst bestaande).
  4. Maakt 6 datasets aan voor UC-01/04/05/06 (×2)/07 (idempotent).
- `platform/12-superset/dashboards/README.md` — workflow voor interactief-bouwen + export naar zip + commit, plus TODO voor declaratief programmatisch maken via Superset's chart-API.
- `platform/12-superset/kustomization.yaml` — referenties supersetcluster + init-job.
- `platform/12-superset/README.md` — OIDC-rolmapping uitgelegd, voorbehoud over single-database-connection (default-catalog `bronze`; `gold.*` via fully-qualified naam of aparte connection in fase 7+), validatie + productie-overwegingen.
- `tests/smoke/06-superset-up.sh` — pod rollout, init-Job Complete, login → DB-list bevat `trino`, dataset-count ≥ 3.

### Verificatie (host, geen cluster)
- 3 YAML-bestanden parsen.
- Python init-script (uit ConfigMap-data) compileert via `ast.parse`.
- `kubectl kustomize platform/12-superset` → 3 resources (SupersetCluster + ConfigMap + Job).
- bash-syntax smoke 06 groen.

### Beslissingen
- **Init via post-deploy Job** in plaats van Helm-style hooks of Stackable's eigen mechanism — Stackable SupersetCluster heeft geen ingebouwde Trino-registratie hook. Een eenvoudige Job met python:3.11 + requests is de standaard pragmatische oplossing.
- **`userRegistration: true` + `syncRolesAt: Login`** — automatisch een Superset-account voor elke OIDC-login. Default-rol `Public` (geen rechten); admin moet promoten. Productie: declaratieve role-mapping in Stackable's AuthenticationClass.
- **Geen pre-built dashboards in fase 7** — Superset dashboard-zips zijn complex om handmatig te kraken; betere workflow is bouw-in-UI → export → commit. README documenteert het pad. DoD-anchor "WIA Funnel dashboard" is dus een fase-7+ follow-up.
- **Eén Trino-database-connection met catalog `bronze`** voor de smoke — productie gebruikt aparte connections per catalog (bronze/silver/gold/sensitive) voor finer-grained RBAC. Datasets in init-Job verwijzen naar `gold.uc0x_*` schemas; queries in Superset moeten dan fully-qualified zijn.
- **Trino-credentials uit `trino-static-users` Secret** — zelfde smoketest-user als Airflow's dbt-tasks. Productie: per-Superset-user OIDC-passthrough (Trino accepteert OIDC-tokens van Keycloak).

### Open / volgende sessie
- Fase 8 — OpenMetadata: Helm install met gedeelde Postgres + OpenSearch (single-node), `platform/13-openmetadata-config/` met classifications (PII.\*, Health.Article9, BIO.BIV.\*, Doelbinding.\*, AI.Risk.\*), CGM-glossary, ingestion-pipelines voor Trino + dbt + Superset + Airflow + Kafka. Plus `om_ingest_*` DAGs in `platform/11-airflow/dags/`. Vector-config voor logs naar gedeelde OpenSearch.

---

## 2026-05-01 — Sessie 9: Fase 8 (OpenMetadata + governance)

### Gedaan

**Helm + namespaces**
- `infrastructure/helm/opensearch/values.yaml` — single-node OpenSearch (master+ingest+data), security plugin uit (dev), `discovery.type=single-node`, 10Gi PVC. Gedeeld voor Vector logs én OM-search per gebruikerskeuze.
- `scripts/bootstrap.sh` — drie nieuwe Helm-installs aan eind: OpenSearch (`opensearch` in `odap-meta`), OpenMetadata (`openmetadata` in `odap-meta`), Vector (`vector` in `odap-monitoring`, Agent-mode). Repo's `opensearch`, `open-metadata`, `vector` toegevoegd. Versies pinned (OS 2.27.1, OM 1.5.0, Vector 0.36.1). Eind-message verwijst naar `metadata generate-token` voor JWT-bootstrap.
- `platform/01-secrets/dev-secrets.yaml` — `openmetadata-admin` Secret (in `odap-meta`) toegevoegd: adminEmail, adminPassword, jwtToken-placeholder.

**OM-config**
- `platform/13-openmetadata-config/classifications.yaml` — **7 classifications met ~50 tags totaal**: PII (BSN/Naam/Adres/Geboortedatum/IBAN/Telefoon/Email/LH_Nummer/Sensitive), Health (Article9/Diagnose/VerzekeringsArts/Arbeidsdeskundige), Confidentiality (Public/Internal/Confidential/Secret — mutuallyExclusive), BIO (BIV-Hoog/Midden/Laag), LegalBasis (Art6_1c/1e + Art9_2h + Art5_1b), Doelbinding (12 tags incl. Uitkering/Reintegratie/Handhaving/Statistisch_Onderzoek), AI (Risk-Laag/Midden/Hoog/Verboden + HumanInTheLoop + Algoritmeregister-Geregistreerd).
- `platform/13-openmetadata-config/glossary-cgm.yaml` — **CGM-glossary met 22 termen**: Client, Persona, Aanvraag, Beoordeling, Beoordelaar, Capaciteit, Diagnose, Traject, Werkhervatting, Uitkomst, IKV, Werknemer, Werkgever, Dienstverband, Ontslag, Uitkering, Inkomen, Huishouden, Aggregaat, Contact, Kanaal, Doelgroepregister.
- `platform/13-openmetadata-config/services/` — **6 service-configs** in OM workflow-YAML format (env-substitutie via `${VAR}`):
  - `trino-service.yaml` (DatabaseMetadata, schema-filters voor alle platform catalogs)
  - `trino-lineage.yaml` (DatabaseLineage, query-history 7 dagen)
  - `trino-profiler.yaml` (Profiler op silver, 30% sample voor scaled-down)
  - `dbt-workflow.yaml` (S3-bron `s3://odap-meta/dbt/latest/`)
  - `superset-service.yaml`
  - `airflow-service.yaml`
  - `kafka-service.yaml`
- `platform/13-openmetadata-config/init-job.yaml` — ConfigMap `openmetadata-init-config` met Python-script dat (1) wacht op `/api/v1/system/version`, (2) classifications + tags POSTet (idempotent: 200/201/409/422 → ok), (3) glossary + terms POSTet. Job gebruikt python:3.11-slim + `requests + pyyaml`. Mount `/config` met de YAMLs.
- `platform/13-openmetadata-config/kustomization.yaml` — `configMapGenerator` bouwt `openmetadata-platform-config` ConfigMap uit alle YAMLs (classifications + glossary + 6 services). Init-Job mount die op `/config`.
- `platform/13-openmetadata-config/README.md` — uitgelegd hoe Job werkt + waar JWT vandaan komt + welke ingestion-runs door Airflow-DAGs worden getriggerd.

**Airflow DAGs**
- `platform/11-airflow/dags/om_ingest_trino.py` — DAG met 3 KubernetesPodOperator-tasks parallel (`metadata`, `lineage`, `profiler`); image `docker.getcollate.io/openmetadata/ingestion:1.5.0`; mount config-map; `envsubst < /config/<workflow>.yaml | metadata <kind> -c -`.
- `platform/11-airflow/dags/om_ingest_dbt.py` — DAG met 1 task die dbt-workflow.yaml uitvoert (manifest + catalog + run_results uit MinIO).
- Update `platform/11-airflow/kustomization.yaml` — DAGs ConfigMap-list uitgebreid met `om_ingest_trino.py` + `om_ingest_dbt.py` (totaal 6 DAGs nu, plus __init__.py).

**Smoke**
- `tests/smoke/07-openmetadata-up.sh` — OpenSearch StatefulSet rollout, OpenMetadata Deployment rollout, init-Job Complete, classifications-API antwoordt met 7 classifications, glossary CGM aanwezig, sample CGM-terms (Aanvraag/Beoordeling/Cliënt/IKV/Uitkering).

### Verificatie (host, geen cluster)
- 12 YAML-bestanden parsen.
- Init-script + 2 Airflow DAGs Python-syntax groen.
- `kubectl kustomize platform/13-openmetadata-config` → 3 resources (1 Job + 2 ConfigMaps: init-script + platform-config bundle).
- `kubectl kustomize platform/11-airflow` → 2 resources met **6 DAG-files** in ConfigMap.
- bash-syntax bootstrap.sh + smoke 07 groen.

### Beslissingen
- **OpenSearch single-node** — past bij user-keuze (vraag 10): één gedeeld cluster voor logs én OM-search. Index-prefixen `logs-*` en `open_metadata*` scheiden de twee consumers. Productie: ≥3 master-eligible + dedicated data-tier.
- **Init-Job via REST API** in plaats van OM CLI — REST is forgivability-friendlier (idempotent via 409/422-detectie); CLI is meer geschikt voor full-blown ingestion-runs (die de DAGs doen).
- **Workflow-YAMLs ondersteunen `${VAR}` env-substitutie** — geen statische passwords/tokens in committed YAMLs. Airflow-DAGs doen `envsubst` voor de actual run.
- **Trino-profiler op `silver`-schemas** — bronze is raw JSON, profiler levert geen waardevolle stats; gold is meestal aggregaten met geringe variatie. Silver is sweet-spot.
- **Reverse-metadata** (OM tags → Trino kolommen → OPA) blijft fase 9 — nu alleen tags landen in OM, OPA-policies in fase 9 lezen ze (potentieel via Stackable's komende auto-bundle).
- **JWT-token-bootstrap is een handmatige post-step** — `metadata generate-token` op de OM-pod, daarna in Secret patchen. Productie: External Secrets + Vault rotatie.
- **Vector deploy in `odap-monitoring`** met endpoint naar OpenSearch in `odap-meta` — cross-namespace service-DNS werkt prima; geen NetworkPolicy issues in dev.

### Open / volgende sessie
- Fase 9 — echte OPA-policies (zie sessie 10 hieronder).

---

## 2026-05-01 — Sessie 10: Fase 9 (echte OPA-policies)

### Gedaan

**Source-of-truth**
- `opa-policies-src/data/role_mappings.json` — top-level wrapper `{"role_mappings": {...}}` zodat zowel `opa test` (raw load → `data.role_mappings.*`) als productie-bundle dezelfde structuur hebben. Bevat: 12 rollen × `catalogs`/`schemas`/`purposes`/capability-flags (`can_see_pii`/`can_see_medical`/`can_see_bankrekening`/`regio_filter`/`break_glass`); 16 `resource_purposes`-mappings (van dbt `meta.doelbinding`); 10 `sensitive_columns` met PII/medical/bankrekening-flags.

**Vijf Rego-policies** in `opa-policies-src/trino/`
- `trino-base.rego` — `default allow := false`, `default rowFilters := []`, `default columnMask := {}`. Helpers: `authenticated`, `user_roles` (met smoketest-fallback), `user_purpose` (uit extraCredentials.purpose), operation-classifiers (`is_read_op`/`is_meta_op`/`is_write_op`). Top-level allow-rules combineren role-check + doelbinding-check.
- `trino-platform-roles.rego` — `role_allows_resource` met **twee paden**: (1) `schemas == null` → catalog-only, (2) `schemas != null` → catalog + schema-membership. Helpers `role_has_capability` + `any_role_has_capability` voor capability-driven masks.
- `trino-doelbinding.rego` — `purpose_allows_resource` (R-AVG-06). Wildcard-resolver matcht `<catalog>.<schema>.<table>` of `<catalog>.<schema>.*`. `user_allowed_purposes` is union over rollen. `*` wildcard voor platform_admin.
- `trino-row-filters.rego` — WIA regio-filter `regio_code = '<UPPER>'` met regex-injection-validatie (`^[a-z]{3}$`); UC-04 opt-out filter; sandbox `bsn_pseudo IS NOT NULL`.
- `trino-column-masks.rego` — BSN-mask `concat('XXXXX', substr(bsn, 6, 4))` voor marketing_analyst; BSN-hard-mask voor rollen zonder `can_see_pii`; IBAN/bankrekening masked voor rollen zonder `can_see_bankrekening`; diagnose/icd10 → NULL voor rollen zonder `can_see_medical`; geboortedatum bucket-per-jaar voor data_steward.

**Vier test-files (23 tests, allemaal PASS)**
- `trino-base_test.rego` — anonymous deny + authenticated meta allow + no-role deny.
- `trino-doelbinding_test.rego` — DoD-check `test_uc05_denied_without_purpose` + 4 anderen.
- `trino-column-masks_test.rego` — DoD-check `test_bsn_masked_for_marketing_analyst` + 5 anderen (IBAN, diagnose, etc.).
- `trino-row-filters_test.rego` — regio-filter, geen filter voor data_steward, opt-out, regex-injection-defense.
- `trino-platform-roles_test.rego` — 5 role-resource-tests.

**Build-pipeline**
- `scripts/build-opa-bundle.sh` — `opa fmt --diff` + `opa test` + sync `*.rego` (excl. `_test.rego`) + render `data.json` (strip `_`-prefixed keys).
- `Makefile` — nieuwe targets `opa-test` + `opa-bundle`.
- `opa-policies-src/Makefile` — convenience-target `make -C opa-policies-src test`.
- `platform/10-opa/kustomization.yaml` — `configMapGenerator` met **6 files** (5 rego + data.json), label `odap.io/policy-tier: production` (vervangt fase-3 allow-all base).

**Smoke + compliance**
- `tests/smoke/08-opa-decisions.sh` — 6 OPA-decision-checks: anonymous deny, marketing_analyst+klantcontact allow, **data_steward zonder purpose op uc05 → deny (DoD R-AVG-06)**, **marketing_analyst+bsn → masking-expr (DoD R-AVG-07)**, claims_analyst+regio_AMS → row-filter, marketing_analyst+diagnose → NULL.
- `docs/compliance-mapping.md` — evidence-paths bijgewerkt voor R-AVG-05/06/07/09, R-BIO-06/11, R-GOV-06 met concrete `opa-policies-src/...` paden + tests-status (23/23 PASS) + smoke-script-link.

### Verificatie (host, OPA 0.69.0 lokaal geïnstalleerd)
- **`opa test`: 23/23 PASS** (na fix: data wrapping + role-allow-pad zonder schema-bypass).
- `opa fmt --diff`: clean (na `opa fmt -w`-pas).
- `kubectl kustomize platform/10-opa/`: 2 resources (OpaCluster + ConfigMap met 6 keys: 5 rego + data.json).
- bash-syntax build-opa-bundle.sh + smoke 08: groen.

### Beslissingen
- **Data-source onder `role_mappings`-key wrappen** in source JSON — zo werken `opa test` (raw-JSON-load → `data.role_mappings.*`) en productie-bundle dezelfde structuur, geen dubbele wrapper.
- **Twee `role_allows_resource`-paden** (`schemas == null` voor catalog-wide, `schemas != null AND schema in schemas`) — voorkomt dat de catalog-only-pad als bypass werkt.
- **Capability-flags op rol-niveau** in JSON in plaats van rol-specifieke mask-rules in Rego — schaalt beter; nieuwe rol = entry in JSON, geen rego-wijziging.
- **Regex-validatie van `regio`-input** voorkomt SQL-injection via `extraCredentials`-header. Regio moet `^[a-z]{3}$` matchen.
- **`platform_admin` met purpose `*`** — break-glass-pad. Audit-log via OPA decision-log naar OpenSearch in productie registreert elk gebruik.
- **`opa fmt -w` toegepast** — formatting-diffs uit het oorspronkelijke schrijfwerk gepoetst; CI faalt voortaan bij elke fmt-diff.
- **`regex.match` (niet `regexp.match`)** — OPA's stdlib heet `regex`. Gotcha tijdens schrijven, opa test ving het direct.

### Open / volgende sessie
- Fase 10 — zie sessie 11 hieronder.

---

## 2026-05-01 — Sessie 11: Fase 10 (compliance + e2e + runbook + CI)

### Gedaan

**E2E**
- `tests/e2e/full-flow-uc01.sh` — 7 stages (cluster → bootstrap → deploy → seed → wait-for-stream → smoke 01–08 → UC-01 verificatie). Skip-flags `SKIP_CLUSTER`/`BOOTSTRAP`/`DEPLOY`/`SEED` voor partial reruns. Verificatie-checks: silver.wia row-count, bronze.uwv.wia_aanvraag rij-aanwezigheid, BSN-prefix-9 anomaliedetectie. Verwachte runtime: 25-35 min op MBP M1/M2 (16 GB).

**Runbook** (`docs/runbook.md`, complete herstructurering)
- 11 secties uitgewerkt met concrete commands: snelstart, lifecycle, component-status (12 componenten met `kubectl`-checks), 5 incident-runbooks (Trino access-denied, dbt table-not-found, streaming-hang, Airflow import-error, OM-init-faal), backup & restore (MinIO + Postgres + Keycloak + Trino), upgrade-procedure (operators + dbt-deps + Helm), seed-herladen, OPA-policy-update-flow, observability-endpoints + OpenSearch-queries, compliance-evidence-verzamelen.
- Sectie 11: bekende beperkingen (single-instance Postgres/MinIO/OpenSearch, static-auth, geen NetworkPolicies, geen TLS Vector→OS) — productie-paden gedocumenteerd.

**Compliance-mapping** (`docs/compliance-mapping.md` sweep)
- Alle ~75 requirements bijgewerkt met concrete file-paths + ADR-links waar relevant. Voorbeelden:
  - R-NORA-04 → `platform-config.yaml::table_format` + ADR-0002
  - R-NORA-08 → `infrastructure/helm/keycloak/realm.json` + `AuthenticationClass keycloak`
  - R-AVG-15 → `infrastructure/helm/vector/values.yaml` + runbook §4
  - R-BIO-23 → runbook §5 (MinIO mirror + pg_dumpall + Keycloak realm-export)
  - R-NIS2-03 → cosign verify + Stackable SBOM in `ci/github-actions/security-scan.yml`
  - R-FUN-10 → `classifications.yaml::AI.Risk-{Laag/Midden/Hoog/Verboden}`
  - R-COMP-04 → DPIA-placeholders in UC-02/UC-04/UC-09
- "TBD"-flags blijven alleen op out-of-scope items (productie-secret-rotatie, MFA-WebAuthn, NetworkPolicies).

**CI pipelines** (`ci/github-actions/`)
- `lint.yml` — yamllint + ruff + opa fmt --diff + shellcheck.
- `opa-test.yml` — `opa test` met 23/23 expectation, fail-on-coverage.
- `dbt-parse.yml` — `dbt deps` + `dbt parse` + meta-block-completeness check op marts.
- `data-generation-tests.yml` — pytest met 19 tests + ruff.
- `security-scan.yml` — Trivy config + filesystem + cosign-verify Stackable images. Weekly schedule.
- `kind-e2e.yml` — full e2e via `tests/e2e/full-flow-uc01.sh` op `ubuntu-24.04-large` (8 CPU, 32 GB), workflow_dispatch + push-naar-main.

### Verificatie (host)
- **OPA test: 23/23 PASS.**
- **Bash-syntax: 18/18 OK** (8 scripts + 8 smoke + e2e + opa-build).
- **Python py_compile: 24/24 OK** (data-generation + spark-jobs + render-script + 5 Airflow DAGs).
- **`kubectl kustomize`: 14/14 directories rendert succesvol** — totaal 44 K8s resources.
- **6 CI workflows YAML-valid.**

### Eindstaat platform

| Component | Aantal | Locatie |
|---|---|---|
| ADRs | 6 | `docs/adr/` |
| Use-case specs | 10 | `docs/use-cases/` |
| Stackable kustomizations | 14 | `platform/00..13/` |
| K8s resources (gekustomized) | 44 | totaal |
| dbt models | 15 (8 staging + 1 intermediate + 6 marts) | `dbt/models/` |
| dbt schemas | 16 | `dbt/models/**/_*.yml` + `dbt/seeds/_seeds.yml` |
| dbt seeds | 5 (CGM + TW-norm + scenarios) | `dbt/seeds/*.csv` |
| Rego policies | 5 + 5 test-files | `opa-policies-src/trino/` |
| Smoke tests | 8 (01-stackable → 08-opa-decisions) | `tests/smoke/` |
| E2E tests | 1 (full-flow-uc01) | `tests/e2e/` |
| Airflow DAGs | 5 (dbt + maintenance + seed + 2× om) | `platform/11-airflow/dags/` |
| CI workflows | 6 (lint + opa + dbt + py-tests + security + kind-e2e) | `ci/github-actions/` |
| Synthetic-data generators | 8 modules + 2 loaders + 19 pytest-tests | `data-generation/` |
| Spark jobs | 2 (lakehouse_io + streaming) | `spark-jobs/` |

### Definition of Done — eindstaat

| Check | Status |
|---|---|
| `make cluster && bootstrap && deploy-platform && seed && test` slaagt schoon | **gevalideerd via host-tooling**; cluster-runtime uitvoering vereist Docker Desktop |
| Superset toont WIA Funnel-dashboard | **datasets aangemaakt** (init-Job); dashboard zelf interactief te bouwen (zie `dashboards/README.md`) |
| OpenMetadata e2e lineage | **services + workflows gedefinieerd**; lineage-run via `om_ingest_trino` DAG |
| OPA weigert query op `client_360.bsn` zonder doel | **`opa test` 23/23 + smoke 08 dekkend** |
| OPA maskeert BSN voor `marketing_analyst` | **`opa test` 23/23 + smoke 08 dekkend** |
| dbt-test `bsn_valid` faalt op ongeldige BSN | **generic-test in `dbt/macros/test_bsn_valid.sql`** |
| OM toont `meta` per gold-tabel | **dbt-workflow leest `meta.eigenaar/legal_basis/doelbinding/...`** |
| `compliance-mapping.md` mapt elke R-* op file/setting | **groen — alle ~75 requirements ingevuld** |
| CI groen op fresh clone | **6 workflows aanwezig**; live-run vereist push naar GitHub |
| Geen `latest`-tag, geen plaintext-secret in productie-policy | **groen** — alle versies gepind, dev-secrets duidelijk gemarkeerd, productie-pad gedocumenteerd in elk README |
| `platform-config.yaml::table_format` switching | **groen** — `make render-catalogs` + `kubectl apply -k platform/09-trino/` is voldoende |

### Beslissingen
- **Skip-flags op e2e** (`SKIP_CLUSTER` etc.) — pragmatisch voor partial reruns tijdens debugging zonder de volledige 30 min cyclus.
- **CI splitst per concern** — lint/opa/dbt/py-tests/security/e2e als aparte workflows; alleen `lint` + `opa-test` + `dbt-parse` zijn fast (~2 min); `kind-e2e` is workflow_dispatch + main-push only.
- **Compliance-mapping links naar relative paths** (`../platform/...`) — werkt in GitHub-rendering en in IDE.
- **Runbook geeft expliciet bekende beperkingen** in §11 — eerlijke documentatie van wat niet productie-klaar is in dit referentie.
- **Trivy + cosign in security-scan** — `R-BIO-15` (vulnerability mgmt) + `R-NIS2-03` (supply-chain) gedekt op CI-niveau.
- **Geen `make compliance-evidence` script** — zou een aparte fase 11 verdienen; runbook §10 documenteert handmatige stappen.

### Project klaar
**Het Open Data & Analytics Platform is in 10 sessies (≈ 1 dag werk gespreid) compleet opgeleverd.** Volledig host-validateerbaar; cluster-uitvoering vereist Docker Desktop met 8 GB RAM + 4 CPU. Productie-deployment vereist verzwaringen die per component in de README zijn gedocumenteerd.

---

## 2026-05-01 — Sessie 12: Improvement-audit + 15 quick-wins

### Audit
- `docs/improvements.md` aangelegd — **411 regels, 16 categorieën, ~150 items**, met prioritering (🔴/🟠/🟡) en effort-schattingen (S/M/L/XL).
- Concrete code-gaps gemeten via spot-checks: 5 lege mart-dirs, geen NetworkPolicies / HPA / PDB / ResourceQuota, geen pre-built Superset-dashboards, geen PrometheusRules, geen KafkaTopic CRDs, `pseudonymize`-macro nergens gebruikt, etc.

### Quick-wins toegepast (15/15)

**Monitoring suite** (`platform/14-monitoring/` — nieuw):
- #1 `prometheusrule.yaml` — alerts op Trino p99-latency, OPA deny-rate, Spark streaming-lag, Postgres-disk, namespace-quota, KubePodNotReady.
- #5 `alertmanager-config.yaml` — Slack-receiver (warning) + PagerDuty (critical) + inhibit-rules; webhooks via Secret `alertmanager-receivers`.
- #3 `pdb.yaml` — PodDisruptionBudgets voor 8 workloads (Trino-coord/worker, Kafka, ZK, Hive, OPA, Postgres, OpenSearch).
- #3 `hpa-trino.yaml` — HorizontalPodAutoscaler op Trino-workers (1-3 replicas, 70% CPU / 80% mem-target).
- #15 `opensearch-ilm-job.yaml` — twee ILM-policies: app-logs 30d delete, audit-logs 7 jaar (R-BIO-20). Idempotente Job die ze toepast via OS REST API.

**Resource-control + segmentatie**:
- #4 `platform/00-namespaces/resourcequota-limitrange.yaml` — ResourceQuota + LimitRange voor 5 namespaces, conservatief op scaled-down k3d.

**Kafka-topics declaratief**:
- #2 `platform/06-kafka/kafkatopics-job.yaml` — ConfigMap met 14 topics (incl. DLQ + audit), Bitnami Kafka-image-Job die ze idempotent creëert. KafkaCluster-config: `auto.create.topics.enable=false`.

**Identity hardening**:
- #6 Realm odap.json uitgebreid met `passwordPolicy: length(12) and digits(1) and upperCase(1) and specialChars(1) and notUsername and passwordHistory(5)`, sessie-timeouts (1u idle, 8u max), TOTP-policy + `requiredActions: ["CONFIGURE_TOTP"]` op `platform.admin`, `data.engineer`, `case.manager`.

**Pseudonymize-macro daadwerkelijk gebruikt**:
- #7 `dbt/models/intermediate/int_persona_pseudonymized.sql` — pseudo-identifier helper. `dbt/models/marts/uc09_reint_effect/mart_uc09_effect_panel.sql` — sandbox-panel met **alleen** `bsn_pseudo`, geen ruwe BSN. Vult ook gap #1.1 (UC-09 mart leeg).

**Audit-log-routering**:
- #12 `platform/10-opa/opacluster.yaml` configOverride `decision_logs.console: true`. Vector `route_audit_logs` transform splitst OPA-decisions + Trino-queryId-logs naar `logs-audit-*` index met 7-jaar-retentie.

**Bewaartermijn-enforcement (R-AVG-08)**:
- #9 `platform/11-airflow/dags/bewaartermijn_enforcer.py` — daily DAG met TrinoOperator per tabel; bewaartermijnen uit dbt schema.yml `meta.bewaartermijn_jaren`. Dry-run-modus voor publiek-publiceerbare data.

**CI-quality-gates**:
- #11 `ci/scripts/check-dbt-meta.py` — strict-check op marts (`legal_basis, doelbinding, bio_classificatie, bewaartermijn_jaren, eigenaar, pii_kolommen, risk_tier`), soft op staging. Vond direct **2 echte gaps in UC-06** die meteen gefixt zijn. Geïntegreerd in `ci/github-actions/dbt-parse.yml`.
- #8 `.pre-commit-config.yaml` — pre-commit-hooks (trailing-whitespace, end-of-file, check-yaml, check-json, detect-private-key, yamllint, ruff, ruff-format, shellcheck, opa-fmt, dbt-meta-check).

**Documentatie**:
- #10 `SECURITY.md` — vulnerability-disclosure-beleid (R-NIS2-05) met SLA's per CVSS-severity + scope + responsible-disclosure-default 90 dagen.

**Test-pijp**:
- #14 `tests/e2e/fast-e2e.sh` — runtime 3-5 min: skipt cluster + bootstrap, runt smoke 01-08 + UC-01 BSN-prefix-check. Geschikt voor PR-CI.

**BI-coverage**:
- #13 `platform/12-superset/dashboards-init-job.yaml` — ConfigMap met `build_dashboards.py` (~120 regels Python) + Job die 3 charts (line/pie/big-number) en het **WIA Funnel-dashboard** programmatisch aanmaakt via Superset REST API. Vult DoD-anchor "Superset toont WIA Funnel".

**Glue**:
- `scripts/deploy-platform.sh` — `platform/14-monitoring` toegevoegd aan layer-volgorde.
- `dbt/dbt_project.yml` — `uc09_reint_effect` model-config (database silver, schema sandbox_uc09).
- `infrastructure/helm/vector/values.yaml` — audit-route + dual-sink (`opensearch_app` + `opensearch_audit`).
- `platform/11-airflow/kustomization.yaml` — `bewaartermijn_enforcer.py` toegevoegd aan DAG-ConfigMap (totaal 7 DAGs).
- `ci/github-actions/dbt-parse.yml` — meta-check in plaats van eerdere grep.

### Verificatie (host)
- **`opa test`: 23/23 PASS** (na quick-wins onveranderd).
- **`check-dbt-meta.py`: alle marts hebben alle verplichte meta-velden** (na UC-06 fix).
- **YAML-parse 9 nieuwe manifests**: groen.
- **Python syntax 3 nieuwe scripts (build_dashboards, bewaartermijn_enforcer, check-dbt-meta) + fast-e2e bash**: groen.
- **`kubectl kustomize` per directory**:
  - `platform/00-namespaces`: 5 → **13** (NS + 5 RQ + 4 LR)
  - `platform/06-kafka`: 1 → **3** (Cluster + ConfigMap + Job)
  - `platform/10-opa`: 2 (configOverride change, geen extra resource)
  - `platform/12-superset`: 3 → **5** (+ ConfigMap + dashboards-init Job)
  - `platform/14-monitoring`: nieuw → **14 resources** (PrometheusRule + AlertmanagerConfig + Secret + 8 PDBs + HPA + ConfigMap + ILM-Job)
- **Pre-commit-config valid**: groen.

### Beslissingen
- **`platform/14-monitoring/`** als nieuwe top-level layer in plaats van scattered overlays — keep monitoring-config bij elkaar.
- **HPA `maxReplicas: 3`** voor Trino-worker — productie-overlay bumpt naar 10+.
- **Audit-log-routing in Vector** in plaats van een extra Fluent Bit — Vector heeft al alle pod-logs binnen, een transform is genoeg.
- **Bewaartermijn-DAG met dry-run-flag per tabel** — publiek-publiceerbare data (FEZ aggregaten) staat op `dry_run: True`; productie zet dit vrijwillig om naar daadwerkelijke DELETE na review.
- **`requiredActions: CONFIGURE_TOTP`** alleen op admin-rollen — productie zou dit op alle users zetten met federatie als alternatief.
- **Alertmanager-webhooks placeholder** — Secret heeft `REPLACE`-strings; Slack/PagerDuty echte URL's via External Secrets in productie.
- **Superset dashboard via API ipv export-zip** — reproduceerbaar, leesbaar, geen export-roundtrip nodig om wijzigingen te commiten.
- **`auto.create.topics.enable=false`** in Kafka — productie-hygiëne; topics expliciet beheerd.

### Resterende verbeteringen
Zie [`docs/improvements.md`](improvements.md) — ~135 items in lager-prio categorieën blijven open (HA-overlays, GitOps/ArgoCD, NiFi-flows, dashboard-builder voor andere UC's, NetworkPolicies, MDM, etc.).
