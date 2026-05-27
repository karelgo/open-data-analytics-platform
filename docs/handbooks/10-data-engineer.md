# Handbook — Data-engineer

> Rol-key: `data_engineer` · Domein: Data-pipelines & ingestion · Risiconiveau access: hoog (PII in bronze, JIT)

Deze handbook is voor **data-engineers** die pipelines bouwen en
beheren. Je hebt **JIT-access** (just-in-time) tot `bronze.*` voor
debug-doeleinden — niet voor permanent gebruik. Je bouwt NiFi-flows,
Spark-jobs, dbt-models en Airflow-DAGs.

---

--8<-- "_snippets/url-modes.md"

## 1. Wat doet jouw rol?

Je bouwt en onderhoudt de datastromen van bron tot mart. Je gebruikt het
platform om:

- Brondata via NiFi naar Kafka te krijgen
- Spark Structured Streaming jobs te draaien (Kafka → Delta op MinIO)
- dbt-models te bouwen (`silver.*` → `gold.*`)
- Airflow-DAGs voor batch en onderhoud te schedulen
- DQ-tests in te bouwen
- Bronze-data te debuggen wanneer nodig

---

## 2. Sign in, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Apache Airflow** | DAGs maken, runs monitoren | https://airflow.odap.local:8443 |
| **dbt CLI** | Lokaal of in CI | terminal |
| **kubectl + k9s** | Spark-jobs, pod-status, Hive Metastore | terminal |
| **Apache Superset** | Eigen build-dashboards reviewen | https://superset.odap.local:8443 |
| **OpenMetadata** | Service-config, lineage publishing | https://openmetadata.odap.local:8443 |
| **MinIO Console** | Bucket-debugging | https://minio.odap.local:8443 |

- NiFi-flows worden as-code beheerd in `nifi-flows/templates/` en geïmporteerd via `kubectl port-forward` (zie `nifi-flows/templates/delta/README.md`).
- dbt en Airflow benaderen Trino in-cluster; voor ad-hoc debug: `kubectl -n odap-platform port-forward svc/trino-coordinator 8443:8443`.

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs

| Catalog | Access | Hoe? |
|---|---|---|
| `bronze` | **JIT** — moet request | Via Trino, alleen na ticket-id in PR/PR-comment |
| `silver`, `gold` | **Indirect** — via dbt-runs en CI | Niet direct queryen voor business-doel |
| `sensitive`, `sandbox` | **Nee** | Alleen domein-rollen / researcher |

### 3.2 JIT-procedure

1. Ticket aanmaken in tracker (Linear/Jira) met **doel** en **scope**.
2. Platform-admin keurt goed; rol wordt 4 uur geactiveerd voor jouw account.
3. Jouw queries worden gelogd. Na 4 uur deactiveert access automatisch.
4. Voeg ticket-id toe als comment bij elke query (`-- TICKET-1234`).

### 3.3 Welke kolommen?

In `bronze.*`: alles ruw — inclusief BSN, naam, IBAN. Wees uiterst
zuinig: **kijk niet meer dan nodig**.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Nieuwe bron toevoegen

**Scenario.** Beleid vraagt om data van een nieuw bronsysteem `xyz`.

1. **Ontwerp**: schrijf een mini-spec in `docs/use-cases/uc-xyz.md` (entiteiten, classificatie, purpose-limitation, retention period).
2. **NiFi-flow**: kopieer template `nifi-flows/templates/delta/source-xyz/` aan, pas processors aan.
3. **Kafka-topic**: definieer `uwv.xyz.event` in `platform/06-kafka/topics.yaml`.
4. **Spark-job**: voeg `streaming-bronze-xyz.yaml` toe; gebruik helper `lakehouse_io.write_delta()`.
5. **Schema in HMS**: `CREATE TABLE bronze.demo.xyz_events (...) USING DELTA LOCATION 's3a://odap-bronze/xyz/'`.
6. **dbt-stg**: `dbt/models/staging/stg_xyz.sql` met basisvalidatie.
7. **OPA-update**: voeg purpose toe in `data/role_mappings.json::resource_purposes`.
8. **OpenMetadata**: voeg service-config toe (auto-discovery).
9. **CI**: `make opa-test`, `dbt parse`, smoke tests.
10. **PR review** door data-steward + platform-admin.

### 4.2 Workflow B — dbt-model maken

```sql
-- dbt/models/marts/uc_xyz/mart_xyz_daily.sql
{{ config(
    materialized = 'table',
    table_format = table_format_properties()['table_format']
) }}

WITH src AS (
    SELECT * FROM {{ ref('stg_xyz') }}
)
SELECT
    date_trunc('day', event_ts) AS dag,
    COUNT(*)                    AS aantal,
    AVG(value)                  AS gem_value
FROM src
GROUP BY 1
```

Met `schema.yml`:

```yaml
version: 2
models:
  - name: mart_xyz_daily
    meta:
      eigenaar: data.steward@odap.local:8443
      domain: xyz
      legal_basis: art_6_1e
      purpose-limitation: [sturingsinfo]
      retention period_jaren: 7
      pii_kolommen: []
    columns:
      - name: dag
        tests: [not_null]
      - name: aantal
        tests: [not_null]
```

Run: `dbt run --select mart_xyz_daily && dbt test --select mart_xyz_daily`.

### 4.3 Workflow C — Streaming-job debuggen

**Scenario.** Spark-job hangt in `streaming-bronze-wia`.

1. `kubectl get sparkapp -n odap-platform`
2. `kubectl logs -n odap-platform <driver-pod>`
3. Spark UI port-forwarden:
   ```
   kubectl port-forward -n odap-platform svc/spark-streaming-ui 4040:4040
   ```
   Open http://localhost:4040
4. Checkpoint-bucket inspecteren via MinIO Console: `s3://odap-checkpoints/<job>/`
5. Zie [`docs/runbook.md` § 4.3](../runbook.md) voor scenario-stappen.

### 4.4 Workflow D — Pipeline-falen patchen

```bash
# Lokaal testen
make doctor                       # cluster-health
dbt parse --target dev
dbt build --select +mart_failed   # bouw upstream tot en met deze

# Naar cluster
kubectl apply -f platform/08-spark/apps/streaming-bronze-fixed.yaml
```

### 4.5 Workflow E — Onderhoud-DAG (compaction/vacuum)

Airflow-DAG `lakehouse_maintenance` draait dagelijks. Format-aware:

- Delta: `OPTIMIZE` + `VACUUM`
- Iceberg: `expire_snapshots` + `rewrite_data_files`

Bij falen: bekijk de Airflow-task-log; meestal is het MinIO disk-druk of
Hive-metastore lock.

### 4.6 Workflow F — JIT-aanvraag voor bronze

Stel: een dbt-test faalt met `IBAN format invalid`. Je wilt zien hoe de
ruwe IBAN binnenkomt vanuit bronze.

1. Open ticket: "TICKET-1234: debug iban-validatie WIA-aanvraag, bronze access 4u"
2. Platform-admin keurt goed
3. Query met ticket-id:
   ```sql
   -- TICKET-1234
   SELECT iban, COUNT(*)
   FROM   bronze.claims.application_raw
   WHERE  ingest_dag = CURRENT_DATE
   GROUP  BY iban
   LIMIT  20;
   ```
4. Los root-cause op, deploy fix, sluit ticket. Access verloopt automatisch.

---

## 5. Code- en deploy-discipline

- **Geen `latest`-tags.** Pin altijd image-versies; release-pinning in `infrastructure/stackablectl/release.yaml`.
- **Geen plaintext secrets.** Gebruik Stackable secret-operator + Vault (production).
- **Eén ADR per architecturekeuze.** Zie `docs/adr/` voor format.
- **Format-agnostisch.** Geen hardcoded `delta` of `iceberg` buiten de switch-points (zie [docs/architecture.md § 4](../architecture.md)).
- **CI moet groen.** PR's met rode CI worden niet gereviewd.

---

## 6. Hulp, fouten & escalatie

| Probleem | Contact |
|---|---|
| Cluster down | Platform-admin (telefonisch) |
| OPA-policy verandering | Pair met platform-admin + data-steward |
| Schema-mismatch in bronze | Bron-eigenaar (UWV-zijde) |
| Production-incident | Volg [`docs/runbook.md` § 4](../runbook.md) |

| Foutmelding | Actie |
|---|---|
| `Hive metastore connection refused` | `kubectl get hivecluster -A`; restart als nodig |
| `dbt test failed: bsn_valid` | Synthetische generator faalt? Of echte ingestion-fout? |
| `OPA bundle out of date` | `scripts/build-opa-bundle.sh && kubectl apply -f platform/10-opa/` |

---

## 7. Wat je nooit doet

- Permanente access tot `bronze.*` activeren — JIT, altijd JIT.
- Production-data downloaden naar je laptop voor lokaal werk.
- Een Spark-job zonder unit-tests in production deployen.
- Changes in `platform-config.yaml::table_format` zonder ADR.
- Direct `kubectl edit` op production-CRDs — alles via PR + GitOps.

---

**Vorige:** [09-data-steward.md](09-data-steward.md) ·
**Volgende:** [11-platform-admin.md](11-platform-admin.md) ·
**Index:** [README.md](README.md)
