# 03-storage

S3Connection definitie voor MinIO.

| Resource | Doel |
|---|---|
| `S3Connection s3-minio` | Centrale referentie to the in-cluster MinIO. Wordt door HiveCluster, TrinoCluster, SparkApplication en (later) NiFi gebruikt. |

## Apply

```bash
kubectl apply -k platform/03-storage/
```

## Validatie

```bash
kubectl -n odap-platform get s3connection s3-minio -o yaml
```

## Production-overwegingen

- `tls.verification.server.caCert.secretClass` aanzetten (production MinIO heeft TLS).
- `accessStyle: VirtualHosted` als de production object-store dat vereist (AWS S3).
- Per-bucket S3Bucket resources om finer-grained credentials te gebruiken (R-AVG-09 least privilege).
