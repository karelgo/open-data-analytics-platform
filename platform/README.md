# platform/ — Kubernetes-manifests per laag

Eén submap per platform-component. De **numerieke prefix** (`00`–`15`) geeft
de **deploy-volgorde** aan: lagere nummers zijn afhankelijkheden van hogere
nummers. `scripts/deploy-platform.sh` past de mappen in deze volgorde toe.

> Wijzig configuratie zoveel mogelijk centraal in
> [`../platform-config.yaml`](../platform-config.yaml), niet binnen de
> componenten zelf.

## Componenten

| # | Component | Wat | Afhankelijkheden |
|---|---|---|---|
| 00 | [namespaces](00-namespaces/README.md) | Declaratieve namespaces (`odap-platform`, `odap-data`, `odap-monitoring`, …) en netwerk-labels. | — |
| 01 | [secrets](01-secrets/README.md) | Stackable `SecretClass`-CRD's + dev-only `Secret`-objects (Postgres, MinIO, Keycloak admin). | 00 |
| 02 | [authentication](02-authentication/README.md) | `AuthenticationClass` voor Keycloak-OIDC + interne TLS-CA-secretclass. | 00, 01 |
| 03 | [storage](03-storage/README.md) | `S3Connection` voor MinIO + bucket-init Job. | 00, 01 |
| 05 | [hive-metastore](05-hive-metastore/README.md) | Hive Metastore — catalog backend voor zowel Delta als Iceberg. | 00, 01, 03 |
| 08 | [spark](08-spark/README.md) | Spark-on-Kubernetes via `SparkApplication`-CRD; leest JSONL uit s3a://odap-raw/. | 00, 03, 05 |
| 09 | [trino](09-trino/README.md) | Trino — distributed SQL engine met OPA-authz + OIDC. | 00, 02, 03, 05, 10 |
| 10 | [opa](10-opa/README.md) | Open Policy Agent — authorisatielaag voor Trino. | 00 |
| 11 | [airflow](11-airflow/README.md) | Apache Airflow via `AirflowCluster`-CRD; orkestreert dbt + maintenance. | 00, 02, 09 |
| 12 | [superset](12-superset/README.md) | Apache Superset BI via `SupersetCluster`-CRD; querryt Trino. | 00, 02, 09 |
| 13 | [openmetadata-config](13-openmetadata-config/README.md) | UWV-specifieke OpenMetadata-config: classifications, ingestion-pipelines. | OpenMetadata via `infrastructure/helm/` |
| 14 | [monitoring](14-monitoring/README.md) | Cross-cutting reliability: PrometheusRules, ServiceMonitors. | Prometheus via `infrastructure/helm/` |
| 15 | [portal](15-portal/README.md) | Rol-aware launchpad — landingspagina op `https://uwv.odap.local`. | 00, 02 |
| 16 | [jupyter](16-jupyter/README.md) | ODAP Lab — JupyterHub + KubeSpawner; notebook-werkplek op bronze/silver/gold/sensitive met Git-integratie. | 00, 02, 03, 05, 09 |

## Deploy

```bash
make deploy-platform        # past 00..16 in volgorde toe
```

Voor één enkel component:

```bash
kubectl apply -k platform/09-trino/        # of -f bij niet-kustomize componenten
```

## Cluster-modi

`platform-config.yaml#scale_profile` schakelt tussen:

- `scaled-down` — 1 replica per service, lage resource requests (k3d-default).
- `production` — meerdere replicas, hogere requests/limits.

> Kustomize `overlays/` voor de production-flip is nog niet aanwezig — zie
> [`docs/improvements.md`](../docs/improvements.md) item 1.7.

## Conventies

- Elke submap is **kustomize-compatibel** (kustomization.yaml of plain manifests).
- README per component: doel, CRD-overzicht, port-forward, bekende issues.
- Geen geheimen committen — alle Secret-objecten zijn `dev-` gemarkeerd
  en mogen niet naar productie. Zie [`01-secrets/README.md`](01-secrets/README.md).
- `table_format` en andere cross-component-keuzes komen uit
  [`../platform-config.yaml`](../platform-config.yaml).
