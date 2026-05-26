# 03-storage

S3Connection definitie voor MinIO.

| Resource | Doel |
|---|---|
| `S3Connection s3-minio` | Centrale referentie naar de in-cluster MinIO. Wordt door HiveCluster, TrinoCluster, SparkApplication en (later) NiFi gebruikt. |

## Apply

```bash
kubectl apply -k platform/03-storage/
```

## Validatie

```bash
kubectl -n odap-platform get s3connection s3-minio -o yaml
```

## Productie-overwegingen

- `tls.verification.server.caCert.secretClass` aanzetten (productie MinIO heeft TLS).
- `accessStyle: VirtualHosted` als de productie object-store dat vereist (AWS S3).
- Per-bucket S3Bucket resources om finer-grained credentials te gebruiken (R-AVG-09 least privilege).
