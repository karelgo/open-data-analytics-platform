# 05-hive-metastore

Hive Metastore (HMS) als catalog backend voor zowel Delta als Iceberg.

| Resource | Doel |
|---|---|
| `HiveCluster hive` | 1 metastore-pod, Postgres-backed (db `hivemetastore` in `odap-data`). |

## Hoe Hive het Delta/Iceberg-formaat agnostisch ondersteunt

HMS slaat tabel-metadata op (kolommen, partitions, locaties). Het tabelformaat
zit in tabel-properties (`spark.sql.sources.provider=delta` voor Delta;
of `provider=iceberg` voor Iceberg). Trino, Spark en Hive lezen die properties
en weten welke connector te gebruiken. **Hetzelfde HMS** kan dus tabellen
beheren in beide formaten.

## Prerequisites

- `platform/01-secrets/` toegepast (hive-postgres-credentials).
- `platform/03-storage/` toegepast (s3-minio S3Connection).
- `infrastructure/helm/postgresql/` install heeft de `hivemetastore` database aangemaakt (init-script).

## Apply

```bash
kubectl apply -k platform/05-hive-metastore/
```

## Validatie

```bash
kubectl -n odap-platform get hivecluster
kubectl -n odap-platform get pods -l app.kubernetes.io/name=hive
kubectl -n odap-platform logs -l app.kubernetes.io/name=hive --tail=50
```

Test (port-forward + simple thrift query is complex; eenvoudiger via Trino in fase 3).
