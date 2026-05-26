# 11-airflow

Apache Airflow via Stackable's AirflowCluster CRD. Pipeline-architectuur volgens
[**ADR-0007**](../../docs/adr/0007-airflow-pipeline-architecture.md): Cosmos +
Datasets + YAML-source-registry. Eén YAML toevoegen = nieuwe bron in productie.

| Resource | Doel |
|---|---|
| `AirflowCluster airflow` | Webserver + scheduler + KubernetesExecutor, Postgres-backend, OIDC via Keycloak. |
| `ConfigMap airflow-dags` | Mount op `/stackable/airflow/dags` — DAG-aanroeperfiles (factory-calls). |
| `ConfigMap airflow-include` | Mount op `/opt/odap/airflow/include` (PYTHONPATH) — factories + helpers. |
| `ConfigMap airflow-sources` | Mount op `/opt/odap/airflow/sources` — YAML-registry. |
| `ConfigMap dbt-manifest` | Mount op `/opt/odap/dbt/manifest.json` — Cosmos-input, gerenderd door `dbt-manifest-render` Job. |
| `Job dbt-manifest-render` | Eenmalige `dbt parse` + ConfigMap-write. Re-run bij dbt-model-wijziging. |

## Mapstructuur

```
platform/11-airflow/
├── airflowcluster.yaml          # podOverrides voor cosmos-init + 4 mounts
├── kustomization.yaml           # 3 configMapGenerators
├── ingress.yaml
├── dags/                        # DAG-aanroeperfiles — alleen factory-calls
│   ├── ingest_bronze_watch.py
│   ├── transform_silver_per_domain.py     # genereert silver_<domain> × 8
│   ├── transform_gold_per_usecase.py      # genereert gold_<uc>_<name> × 6
│   ├── governance_om_ingest.py
│   ├── bewaartermijn_enforcer.py
│   ├── lakehouse_maintenance.py
│   └── synthetic_data_load.py
├── include/                     # importable factories + helpers
│   ├── sources_loader.py        # YAML → SourceSpec dataclass
│   ├── datasets.py              # bronze://, silver://, gold:// URI-conventies
│   ├── trino_helpers.py
│   ├── k8s_helpers.py
│   ├── bronze_factory.py
│   ├── silver_factory.py        # Cosmos DbtDag op tag:<domain> tag:staging
│   ├── gold_factory.py          # Cosmos DbtDag op tag:uc<NN>
│   └── governance_factory.py
├── sources/                     # YAML — single source of truth per bron
│   ├── persoon.yml … fez.yml    # 8 bestanden
├── jobs/
│   └── dbt-manifest-job.yaml    # genereert manifest.json voor Cosmos
└── tests/
    └── dag_integrity_test.py
```

## DAGs

| DAG | Trigger | Wat |
|---|---|---|
| `bronze_watch` | every 5 min | Per bron: SELECT count + max(kafka_ts) op `bronze.uwv.<table>` afgelopen 24u. Bij niet-leeg en streaming-mode binnen drempel: outlet `Dataset("bronze://uwv/<table>")`. |
| `silver_<domain>` (× 8) | bronze-Dataset van die bron | Cosmos rendert `dbt run+test --select tag:<domain> tag:staging`. Eén Airflow-task per dbt-model. Outlet: `Dataset("silver://<domain>/<entity>")`. |
| `gold_<uc>_<name>` (× 6) | silver-Datasets van alle benodigde bronnen | Cosmos rendert `dbt run+test --select tag:uc<NN>`. UC-05 wacht op 6 silver-Datasets vóór run. |
| `governance_om_ingest` | hourly | OpenMetadata: Trino-catalog → dbt-artifacts (sequentieel). |
| `bewaartermijn_enforcer` | daily | R-AVG-08 enforcer (ongewijzigd). |
| `lakehouse_maintenance` | daily | OPTIMIZE/VACUUM per bronze-tabel (Delta of Iceberg afhankelijk van `TABLE_FORMAT`). |
| `synthetic_data_load` | manueel | Past dezelfde Kubernetes Job toe als `make seed`. |

**Totaal**: 1 bronze-watch + 8 silver + 6 gold + 1 governance + 3 ops = **19 DAGs**.

## Een nieuwe bron toevoegen

1. Voeg `sources/<name>.yml` toe (kopieer een bestaande als template).
2. Schrijf het dbt-staging-model in `dbt/models/staging/<name>/stg_<name>_<entity>.sql` + schema.yml met tag `["staging", "<name>", ...]`.
3. `make airflow-manifest` — re-rendert `dbt-manifest` ConfigMap.
4. `kubectl apply -k platform/11-airflow/` — herlaadt ConfigMaps.
5. Klaar — `bronze_watch` heeft een nieuwe task; `silver_<name>` DAG verschijnt automatisch.

Om de bron in een gold-mart te gebruiken: voeg `<uc>` toe aan `used_by_use_cases` in de YAML; de gold-DAG-trigger past zich automatisch aan.

## Cosmos-installatie

Astronomer-Cosmos wordt door een initContainer `cosmos-init` (image `python:3.12-slim`) pip-geïnstalleerd in een emptyDir-volume `/cosmos-pkgs`. De Airflow-container heeft die op `PYTHONPATH`.

- **Versie**: `astronomer-cosmos==1.12.0` (gepind in `airflowcluster.yaml`).
- **Cold-start kost** ~5s per pod-start. Productie: bouw een custom image (zie `infrastructure/airflow/Dockerfile`, TODO).
- **Modus**: `LoadMode.DBT_MANIFEST` + `ExecutionMode.KUBERNETES`. Geen DB-toegang nodig bij DAG-parse.

## Apply

```bash
# Eenmalig: render dbt manifest.json (vereist Airflow Variable repo_url
# of een ConfigMap odap-repo-url met key=url)
kubectl apply -f platform/11-airflow/jobs/dbt-manifest-job.yaml
kubectl -n odap-platform wait --for=condition=complete --timeout=5m job/dbt-manifest-render

# Daarna: het hele platform-deel
kubectl apply -k platform/11-airflow/
```

## Trino-connection in Airflow

Pre-deploy: maak via Airflow UI Admin → Connections de connectie `trino_default`:

```
Conn Type:   Trino
Host:        trino-coordinator.odap-platform.svc.cluster.local
Port:        8443
Login:       smoketest
Password:    <waarde uit Secret trino-static-users.smoketest>
Schema:      bronze
Extra:       {"protocol": "https", "verify": false}
```

Cosmos `TrinoCertificateProfileMapping` leest deze uit (zie `silver_factory._profile_config`).

## Tests

```bash
# Host-validatie zonder cluster
cd platform/11-airflow
SOURCES_DIR=$PWD/sources PYTHONPATH=$PWD/include \
  python3 -m pytest tests/

# Wat de test dekt:
#   - 8 YAMLs parsen tot SourceSpec
#   - Geen duplicate topics / bronze-tabellen
#   - Dataset-URIs goed gevormd
#   - UC-05 heeft 6 silver-deps (anti-regressietest)
#   - DAG-files importen (vereist airflow op host)
#   - Cosmos-availability check
```

## Migratie vanaf de oude `dbt_run_per_domain.py`

`dbt_run_per_domain.py`, `om_ingest_trino.py` en `om_ingest_dbt.py` zijn vervangen door
de factory-DAGs en mogen worden verwijderd zodra alle 6 actieve gold-DAGs een groene run hebben.

## Productie-aanbevelingen

- Custom Airflow-image met cosmos baked-in (vermijd 20s init-container).
- `dagsGitSync` + branch-protection in plaats van ConfigMap-mounts.
- Manifest-render in CI (post-merge op `main`) i.p.v. handmatig Job runnen.
- `webservers.replicas: 2+` voor HA.
- Externe Postgres met daily backup.
- Secrets via External Secrets Operator + Vault.
- Auth: alleen OIDC (verwijder admin-flow).
