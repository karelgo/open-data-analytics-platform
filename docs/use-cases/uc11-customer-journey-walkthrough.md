# UC-11 — Walkthrough & Platform-tour

**Voor wie**: jezelf, demo-publiek, nieuwe collega's. Doel: stap-voor-stap door UC-11
heen wandelen on the draaiende platform, met directe links naar elk onderdeel.

> Inhoudelijke UC-beschrijving: zie [uc11-customer-journey.md](uc11-customer-journey.md).
> Dit document is de **rondleiding** — wat staat waar, welke URL toont wat.

---

## 0. Voordat je begint

### 0.1 Hosts-file

Het platform draait op `*.odap.local:8443` (k3d-cluster met
self-signed certs). Zorg dat je `/etc/hosts` deze entries heeft (één regel
volstaat — IP wijst to the ingress-controller):

```
127.0.0.1   platform.odap.local:8443 keycloak.odap.local:8443 airflow.odap.local:8443 superset.odap.local:8443 openmetadata.odap.local:8443 minio.odap.local:8443 minio-console.odap.local:8443 grafana.odap.local:8443 prometheus.odap.local:8443 opensearch.odap.local:8443
```

Cluster up? Check via `kubectl get ingress -A` of:

```bash
make doctor                 # tooling-check
kubectl -n odap-platform get pods | grep -v Running   # alles Running?
```

### 0.2 Demo-rollen (Keycloak)

Voor UC-11 zijn deze accounts het meest interessant — elk laat een ander
deel van dezelfde mart zien:

| Account | Rol | Wat UC-11 toont |
|---|---|---|
| `marketing.analyst` | `marketing_analyst` | BSN gemaskeerd, event_label gesanitized (geen medisch) |
| `claims.analyst` | `claims_analyst` | volledige medische events, regio-filter actief |
| `fraud.analyst` | `fraud_analyst` | financiële + werkgever-events, medische **deny** |
| `data.steward` | `data_steward` | aggregated view voor DQ-reviews |
| `smoketest` | `smoketest` | technische runner — schrijft de marts |

Wachtwoorden in [`infrastructure/helm/keycloak/realm.json`](../../infrastructure/helm/keycloak/realm.json)
(dev-only).

---

## 1. De platformkaart

| Onderdeel | URL (lokaal) | UC-11 rol |
|---|---|---|
| **Portal** (deze docs + dbt-docs + architecture) | https://platform.odap.local:8443/ | startpunt; lineage-viewer |
| **dbt docs** (lineage, kolom-metadata, tests) | https://platform.odap.local:8443/dbt-docs.html | toon graaf van `mart_uc11_*` ← intermediate ← 7 staging |
| **OpenMetadata** (catalog, glossary, tags, lineage) | https://openmetadata.odap.local:8443 | CGM-glossary `Customer journey`, purpose-limitation-tags |
| **Superset** (BI / dashboards) | https://superset.odap.local:8443 | customer journey-tijdlijn-dashboard |
| **Airflow** (orkestratie) | https://airflow.odap.local:8443 | DAG `gold_uc11_customer_journey` |
| **Keycloak** (SSO + rollen) | https://keycloak.odap.local:8443 | rol-switch, realm-export |
| **MinIO console** (lakehouse buckets) | https://minio-console.odap.local:8443 | bronze/silver/gold/sensitive Delta-bestanden |
| **Grafana** (metrics) | https://grafana.odap.local:8443 | Trino/OPA latency tijdens demo |
| **OpenSearch** (audit-logs) | https://opensearch.odap.local:8443 | "wie keek wanneer" |

> Niet bereikbaar in browser? Zie [Troubleshooting](#7-troubleshooting).

---

## 2. UC-11 in 10 stappen — de demo-volgorde

Een logische volgorde for a presentatie. Volg deze links in een nieuw
tabblad terwijl je vertelt.

### Stap 1 — Het verhaal van Saskia

Open [docs/use-cases/uc11-customer-journey.md](uc11-customer-journey.md). Vertel de
customer journey: werknemer → ziek → WIA → reintegration → werkhervatter.
Geen technologie — alleen het probleem.

### Stap 2 — De architecture op één pagina

Open https://platform.odap.local:8443/architecture. Wijs aan: 7
domeinen, medallion, sensitive bucket, cross-cutting auth/audit. Sluit af
met "alles wat we straks zien is dit plaatje in detail".

### Stap 3 — De data-graaf in dbt docs

Open https://platform.odap.local:8443/dbt-docs.html. Zoek
`mart_uc11_journey_events` → klik linksonder on the **lineage-icoon**.
De graaf toont:

```
stg_persons         ┐
stg_policy_holders    │
stg_service_request_application     │
stg_incident_report      ├─► int_customer_journey_events ─► mart_uc11_journey_events ─► mart_uc11_journey_phases
stg_claim_application    │
stg_eligibility_case  │
stg_customer_interaction     ┘
```

**Vertel**: "alle bronnen waren er al — UC-11 voegt alleen het mart toe dat
de tijdlijn reconstrueert."

### Stap 4 — Catalog & purpose-limitation-tags in OpenMetadata

Open https://openmetadata.odap.local:8443. Navigeer:
**Glossaries → CGM → Customer journey**. Toon de relatie tussen `Customer journey`,
`Fase`, `EventStream` en bestaande CGM-termen (`Cliënt`, `IKV`, `Contact`...).

Daarna **Tables → trino.gold.uc11_customer_journey.mart_uc11_journey_events** →
tabblad **Lineage** for a tweede lineage-view (dezelfde graaf, andere
tool). Tabblad **Sample Data** toont een paar rijen.

### Stap 5 — Eén query, zes brillen (live OPA-demo)

Zet eerst een port-forward op: `kubectl -n odap-platform port-forward svc/trino-coordinator 8443:8443`.
Open vervolgens https://localhost:8443. Login als `smoketest`. Run:

```sql
SELECT bsn, event_ts, domein, event_type, event_label, regio_code
FROM gold.uc11_customer_journey.mart_uc11_journey_events
ORDER BY bsn, event_ts
LIMIT 20;
```

Toon alle kolommen ongemaskeerd (smoketest heeft `can_see_pii`). Log dan uit
en in als `marketing.analyst` (purpose header `customer interaction` zetten in client).
Run dezelfde query → `bsn` gemaskeerd, `event_label` vervangen door
`<domein>.<event_type>`. Login als `claims.analyst` met `regio=AMS` →
alleen rows met `regio_code IN ('AMS', NULL)`.

**Dit is het kernmoment**: één tabel, één query, fundamenteel andere
weergave — niet via aparte views maar via OPA-policy.

### Stap 6 — Fase-reconstructie

Run:

```sql
SELECT bsn, fase_volgnr, fase, fase_start_ts, fase_eind_ts, duur_dagen, is_lopend
FROM gold.uc11_customer_journey.mart_uc11_journey_phases
WHERE bsn = '<vul BSN met meeste events in>'
ORDER BY fase_volgnr;
```

Toon hoe één cliënt door werknemer → ziek → wia → werkhervatter ging,
met doorlooptijden in dagen.

### Stap 7 — Orchestratie in Airflow

Open https://airflow.odap.local:8443. Zoek DAG
`gold_uc11_customer_journey`. Toon:
- Cosmos heeft per dbt-model een task gegenereerd
- Triggers: 7 silver-datasets (één per staging-domein)
- Test-task na elke model-task

Klik op een succesvolle run → **Graph View** → toon volgorde:
staging-tags → intermediate → marts → tests.

### Stap 8 — Audit & glass-box

Demo-foutpoging: laat `marketing.analyst` proberen `numeric_value` op een
WIA-event te selecteren (waar `arbeidsongeschikt_pct` in zou zitten).
Of: query `sensitive.wia.medisch_dossier`. → OPA `deny`.

Open https://opensearch.odap.local:8443 (of de Vector-index in
OpenMetadata) → zoek op `marketing.analyst` in de laatste minuut → de poging
staat geregistreerd met user, rol, queried table, denied=true.

### Stap 9 — Self-service access-request

Open https://openmetadata.odap.local:8443 →
**trino.gold.uc11_customer_journey** → knop **Request Access**. Toon de
[access-request-guide](../access-request-guide.md): vraag wordt door
data-steward goedgekeurd → de
[OM-access-bridge](../../platform/18-om-access-bridge/) zet automatisch
een realm-role `data_access:gold.uc11_customer_journey` in Keycloak.

### Stap 10 — De kosten

Sluit af on the portal-homepage: "dit hele platform draait nu op één
laptop in een k3d-cluster. Eén `make portal-publish-dbt-docs` en de docs
zijn live. Geen cloud-bill — net zoals een production-deploy op AKS er
verder uitziet."

---

## 3. Architecture — per laag, waar in de repo

Volgt de dataflow van bron naar consument. **Klik door** om de code te zien.

### 3.1 Bron → Kafka — data-generatie

Geen nieuwe generator voor UC-11; we hergebruiken de bestaande:

| Domein | Generator | Kafka-topic |
|---|---|---|
| persoon | [data-generation/generators/persona.py](../../data-generation/generators/persona.py) | `customers.created` |
| polisadm | [polisadministratie.py](../../data-generation/generators/polisadministratie.py) | `customers.policy` |
| ww | [ww.py](../../data-generation/generators/ww.py) | `service_requests.application` |
| zw | [zw.py](../../data-generation/generators/zw.py) | `incidents.report` |
| wia | [wia.py](../../data-generation/generators/wia.py) | `claims.application` |
| wajong | [wajong.py](../../data-generation/generators/wajong.py) | `eligibility_cases.case` |
| crm | [crm.py](../../data-generation/generators/crm.py) | `customers.interaction` |

Loader: [data-generation/load_to_kafka.py](../../data-generation/load_to_kafka.py).
Aanroepen via `make seed` (zie [scripts/seed.sh](../../scripts/seed.sh)).

Live explore: `kubectl -n odap-platform port-forward svc/nifi-node-default 8443:8443` en open `https://localhost:8443/` → flow per topic.

### 3.2 Kafka → bronze Delta — Spark Structured Streaming

[spark-jobs/streaming_kafka_to_lakehouse.py](../../spark-jobs/streaming_kafka_to_lakehouse.py)
schrijft elke topic in een Delta-tabel onder `bronze.*`.

Live explore: https://minio-console.odap.local:8443 →
bucket `odap-bronze` → onder `<domain>_<event>/` zie je Delta `_delta_log/`
+ parquet-files.

### 3.3 bronze → silver — dbt staging (views)

Eén view per bron in [dbt/models/staging/](../../dbt/models/staging/):

- [stg_persons.sql](../../dbt/models/staging/persona/stg_persons.sql)
- [stg_policy_holders.sql](../../dbt/models/staging/polisadm/stg_policy_holders.sql)
- [stg_service_request_application.sql](../../dbt/models/staging/ww/stg_service_request_application.sql)
- [stg_incident_report.sql](../../dbt/models/staging/zw/stg_incident_report.sql)
- [stg_claim_application.sql](../../dbt/models/staging/wia/stg_claim_application.sql)
- [stg_eligibility_case.sql](../../dbt/models/staging/wajong/stg_eligibility_case.sql)
- [stg_customer_interaction.sql](../../dbt/models/staging/crm/stg_customer_interaction.sql)

### 3.4 silver → intermediate — UNION ALL naar event-stream

[dbt/models/intermediate/int_customer_journey_events.sql](../../dbt/models/intermediate/int_customer_journey_events.sql)
unifieert de 7 bronnen naar één schema:
`(bsn, event_ts, event_date, domein, event_type, event_label, event_status, regio_code, numeric_value, source_ref_id)`.

### 3.5 intermediate → gold — marts

Beide in [dbt/models/marts/uc11_customer_journey/](../../dbt/models/marts/uc11_customer_journey/):

- [mart_uc11_journey_events.sql](../../dbt/models/marts/uc11_customer_journey/mart_uc11_journey_events.sql) — event-stream met `event_seq` per BSN
- [mart_uc11_journey_phases.sql](../../dbt/models/marts/uc11_customer_journey/mart_uc11_journey_phases.sql) — gaps-and-islands fase-reconstructie
- [_uc11.yml](../../dbt/models/marts/uc11_customer_journey/_uc11.yml) — schema, kolom-tests, meta-tags

Schema-config in [dbt/dbt_project.yml](../../dbt/dbt_project.yml) onder
`uc11_customer_journey: +schema: uc11_customer_journey`.

### 3.6 Autorisatie — OPA Rego

In [opa-policies-src/trino/](../../opa-policies-src/trino/):

- [trino-row-filters.rego](../../opa-policies-src/trino/trino-row-filters.rego) — UC-11 regel: claims_analyst regio-filter + fraud_analyst medisch-filter
- [trino-column-masks.rego](../../opa-policies-src/trino/trino-column-masks.rego) — UC-11 regel: event_label + source_ref_id sanitization
- [trino-row-filters_test.rego](../../opa-policies-src/trino/trino-row-filters_test.rego) + [trino-column-masks_test.rego](../../opa-policies-src/trino/trino-column-masks_test.rego) — UC-11 unit-tests

Gedeployed via [scripts/build-opa-bundle.sh](../../scripts/build-opa-bundle.sh)
naar [platform/10-opa/policies/](../../platform/10-opa/policies/).

### 3.7 Orkestratie — Airflow + Cosmos

UC-11 staat in [platform/11-airflow/include/gold_factory.py](../../platform/11-airflow/include/gold_factory.py)
in `ACTIVE_USE_CASES`. Silver-dependencies komen from the 7 source-YAMLs
onder [platform/11-airflow/sources/](../../platform/11-airflow/sources/)
(`used_by_use_cases: [..., uc11]`).

### 3.8 Catalog + lineage — OpenMetadata

Glossary-uitbreiding in
[platform/13-openmetadata-config/glossary-cgm.yaml](../../platform/13-openmetadata-config/glossary-cgm.yaml):
termen `Customer journey`, `Fase`, `EventStream`. Wordt geladen door de
init-job [init-job.yaml](../../platform/13-openmetadata-config/init-job.yaml).

### 3.9 Consumptie — Superset

Trino-datasource auto-geregistreerd. Dashboard `UC-11 Customer journey` bouw je
interactief in Superset; exporteer als `.zip` naar
[platform/12-superset/dashboards/](../../platform/12-superset/) voor
herhalbare deploy.

---

## 4. Bestandsindex (alles van UC-11 op één plek)

**Documentation**
- [docs/use-cases/uc11-customer-journey.md](uc11-customer-journey.md) — technische UC-beschrijving
- [docs/use-cases/uc11-customer-journey-walkthrough.md](uc11-customer-journey-walkthrough.md) — *dit document*

**dbt**
- [dbt/models/intermediate/int_customer_journey_events.sql](../../dbt/models/intermediate/int_customer_journey_events.sql)
- [dbt/models/intermediate/_intermediate.yml](../../dbt/models/intermediate/_intermediate.yml) (`int_customer_journey_events`-tests)
- [dbt/models/marts/uc11_customer_journey/mart_uc11_journey_events.sql](../../dbt/models/marts/uc11_customer_journey/mart_uc11_journey_events.sql)
- [dbt/models/marts/uc11_customer_journey/mart_uc11_journey_phases.sql](../../dbt/models/marts/uc11_customer_journey/mart_uc11_journey_phases.sql)
- [dbt/models/marts/uc11_customer_journey/_uc11.yml](../../dbt/models/marts/uc11_customer_journey/_uc11.yml)
- [dbt/dbt_project.yml](../../dbt/dbt_project.yml) (schema-config)

**OPA**
- [opa-policies-src/trino/trino-row-filters.rego](../../opa-policies-src/trino/trino-row-filters.rego)
- [opa-policies-src/trino/trino-row-filters_test.rego](../../opa-policies-src/trino/trino-row-filters_test.rego)
- [opa-policies-src/trino/trino-column-masks.rego](../../opa-policies-src/trino/trino-column-masks.rego)
- [opa-policies-src/trino/trino-column-masks_test.rego](../../opa-policies-src/trino/trino-column-masks_test.rego)
- [scripts/opa-test-data-wrap.py](../../scripts/opa-test-data-wrap.py) (Stackable-pad-wrapper voor `opa test`)

**Airflow**
- [platform/11-airflow/include/gold_factory.py](../../platform/11-airflow/include/gold_factory.py) (UC-11 in `ACTIVE_USE_CASES`)
- [platform/11-airflow/sources/persoon.yml](../../platform/11-airflow/sources/persoon.yml)
- [platform/11-airflow/sources/polisadm.yml](../../platform/11-airflow/sources/polisadm.yml)
- [platform/11-airflow/sources/ww.yml](../../platform/11-airflow/sources/ww.yml)
- [platform/11-airflow/sources/zw.yml](../../platform/11-airflow/sources/zw.yml)
- [platform/11-airflow/sources/wia.yml](../../platform/11-airflow/sources/wia.yml)
- [platform/11-airflow/sources/wajong.yml](../../platform/11-airflow/sources/wajong.yml)
- [platform/11-airflow/sources/crm.yml](../../platform/11-airflow/sources/crm.yml)

**OpenMetadata**
- [platform/13-openmetadata-config/glossary-cgm.yaml](../../platform/13-openmetadata-config/glossary-cgm.yaml) (CGM-termen `Customer journey`, `Fase`, `EventStream`)

**Tests**
- [tests/smoke/11-uc11-customer-journey.sh](../../tests/smoke/11-uc11-customer-journey.sh) — cluster-loos
- [tests/e2e/uc11-flow.sh](../../tests/e2e/uc11-flow.sh) — full-flow met cluster

**Makefile targets**
- `make test-uc11` — UC-11 OPA rego-tests
- `make dbt-build-uc11` — dbt run + test op tag:uc11 (cluster nodig)
- `make e2e-uc11` — UC-11 e2e
- `make dbt-docs-offline` — genereer dbt-docs zonder warehouse
- `make portal-publish-dbt-docs` — dbt-docs → image → rollout (k3d)

---

## 5. Hoe verander je iets aan UC-11

### Een kolom toevoegen aan de event-mart

1. Voeg de kolom toe in
   [int_customer_journey_events.sql](../../dbt/models/intermediate/int_customer_journey_events.sql)
   voor elke `<domein>_evt` CTE (zelfde type, NULL waar niet van toepassing).
2. Voeg toe aan de SELECT in
   [mart_uc11_journey_events.sql](../../dbt/models/marts/uc11_customer_journey/mart_uc11_journey_events.sql).
3. Voeg een column-entry toe in [_uc11.yml](../../dbt/models/marts/uc11_customer_journey/_uc11.yml).
4. `make dbt-build-uc11` (vereist cluster).
5. `make portal-publish-dbt-docs` om dbt-docs te updaten on the platform.

### Een fase toevoegen

In [mart_uc11_journey_phases.sql](../../dbt/models/marts/uc11_customer_journey/mart_uc11_journey_phases.sql)
breid het `case ... when event_type = ... then '<nieuwe_fase>'`-blok uit.
Voeg de nieuwe waarde toe aan de `accepted_values`-test in
[_uc11.yml](../../dbt/models/marts/uc11_customer_journey/_uc11.yml).

### Een nieuwe rol-projectie

In [trino-column-masks.rego](../../opa-policies-src/trino/trino-column-masks.rego)
of [trino-row-filters.rego](../../opa-policies-src/trino/trino-row-filters.rego)
voeg een regel toe, schrijf een test in `*_test.rego`. Run:

```bash
make opa-test        # 33/33 PASS
make opa-bundle      # build + sync naar platform/10-opa/policies/
kubectl apply -k platform/10-opa/   # deploy bundle to the cluster
```

Wacht ~30s tot Stackable's bundle-loader het opgepikt heeft.

### Een nieuw domein toevoegen aan de customer journey

1. Voeg generator toe in `data-generation/generators/<nieuw>.py`.
2. Maak source-YAML in `platform/11-airflow/sources/<nieuw>.yml` met
   `used_by_use_cases: [..., uc11]`.
3. Maak staging-model `dbt/models/staging/<nieuw>/stg_<nieuw>.sql`.
4. Voeg `<nieuw>_evt`-CTE toe aan `int_customer_journey_events.sql`.
5. `make dbt-build-uc11 && make portal-publish-dbt-docs`.

---

## 6. Periodieke updates on the platform

```bash
# Volledig opnieuw zaaien (bestaande events behouden, nieuwe events ingestion):
make seed

# Alleen UC-11 marts herbouwen:
make dbt-build-uc11

# dbt-docs on the platform actueel houden (na model-wijzigingen):
make portal-publish-dbt-docs

# OPA-policies hergeneren + deployen (na rego-wijzigingen):
make opa-bundle && kubectl apply -k platform/10-opa/
```

---

## 7. Troubleshooting

### Kan de portal niet openen / certificaatwaarschuwing

Self-signed CA. One-off accepteren in de browser, of importeer
`~/.odap-platform-ca.crt` in je systeem-keystore. Zie
[docs/runbook.md](../runbook.md).

### dbt-docs on the platform is verouderd

```bash
make portal-publish-dbt-docs
```

### "Cluster bereikbaar maar `kubectl exec` faalt met 502"

K3d kubelet-API issue (één agent-node onbereikbaar). Workaround:
herstart k3d-cluster of gebruik de andere worker-node. Zie
[runbook.md](../runbook.md) sectie "k3d node troubles".

### OPA-policy lijkt niet actief

Bundle deployed?
```bash
diff platform/10-opa/policies/trino-row-filters.rego \
     opa-policies-src/trino/trino-row-filters.rego
```

Geen diff = bundle in repo gesynced. Cluster-side:
```bash
kubectl -n odap-platform get cm opa-trino-bundle -o jsonpath='{.metadata.annotations}'
```

Vergelijk `kubectl.kubernetes.io/last-applied-configuration` timestamp met
je laatste `make opa-bundle && kubectl apply -k platform/10-opa/`. OPA's
bundle-loader herpolt elke 20s; geef het een halve minuut.

### `make opa-test` faalt

```bash
# Pad-issue tussen test-env en Stackable production-bundle.
# De wrapper script lost dit op:
python3 scripts/opa-test-data-wrap.py --dst /tmp/opa-test-data.json
opa test opa-policies-src/trino/ /tmp/opa-test-data.json -v
```

Verwacht `PASS: 33/33`.

### Geen rows in `gold.uc11_customer_journey.*`

Marts zijn nooit gebouwd. Trigger Airflow DAG `gold_uc11_customer_journey` of
run lokaal:

```bash
make dbt-build-uc11
```

### Welke BSN heeft de rijkste customer journey?

```sql
SELECT bsn, COUNT(*) AS n_events, COUNT(DISTINCT domein) AS n_domeinen
FROM gold.uc11_customer_journey.mart_uc11_journey_events
GROUP BY bsn
ORDER BY n_domeinen DESC, n_events DESC
LIMIT 5;
```

Gebruik deze als "Saskia" in je demo.

---

## 8. Verder lezen

- [docs/architecture.md](../architecture.md) — algemene platform-architecture
- [docs/handbooks/00-handboek.md](../handbooks/00-handboek.md) — per-rol handbooken
- [docs/access-request-guide.md](../access-request-guide.md) — hoe een gebruiker access aanvraagt
- [docs/compliance-mapping.md](../compliance-mapping.md) — R-GDPR/ISO27001/NIS2/NIS2 → bestand
- [docs/adr/](../adr/) — architecturebeslissingen
- [docs/runbook.md](../runbook.md) — operations
