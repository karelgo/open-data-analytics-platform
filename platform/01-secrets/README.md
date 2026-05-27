# 01-secrets

Stackable SecretClasses + Kubernetes Secrets for the ODAP platform.

| Resource | Functie |
|---|---|
| `SecretClass s3-credentials-minio` | Verbindt MinIO-credentials met Stackable-operators (Hive, Trino, Spark, NiFi). |
| `SecretClass oidc-client-credentials` | Verbindt OIDC-client-secrets met Stackable-services. |
| `Secret minio-s3-credentials` | accessKey + secretKey voor MinIO. |
| `Secret hive-postgres-credentials` | Postgres-wachtwoord voor HMS. |
| `Secret <svc>-oidc-client` | Per service (trino/superset/airflow/nifi) een OIDC client-secret. |
| `Secret airflow-postgres-credentials` | Adminuser + DB-wachtwoord (fase 6). |
| `Secret superset-postgres-credentials` | Adminuser + DB-wachtwoord (fase 7). |

## Production-pad (TODO ADR)

Vervang `dev-secrets.yaml` door:
- **SealedSecrets** (Bitnami) of **SOPS** (Mozilla) voor at-rest-encryptie in Git, of
- **external-secrets-operator** met Vault als bron, of
- **Stackable secret-operator** met `k8sSearch` op een door Vault gevulde Secret.

Production-Secret-rotatie: documenteer in `docs/runbook.md` § 5 (Backup/restore)
en koppel aan R-BIO-08 in [`docs/compliance-mapping.md`](../../docs/compliance-mapping.md).

## Apply

```bash
kubectl apply -k platform/01-secrets/
```

## Validatie

```bash
kubectl get secretclass
kubectl get secrets -n odap-platform -l odap.io/dev-only=true
```
