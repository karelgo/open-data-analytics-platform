# Trino catalogs

Vier catalogs (bronze, silver, gold, sensitive) komen voort uit de
medallion-architecture + Sensitive Vault uit
[`docs/architecture.md`](../../../docs/architecture.md#3-zone-scheiding-medallion--sensitive).

## Format-rendering

Templates (`*.yaml.tmpl`) bevatten twee placeholders:

| Placeholder | Vervangen door |
|---|---|
| `__TABLE_FORMAT__` | `delta` of `iceberg` (uit `platform-config.yaml`) |
| `__TABLE_FORMAT_CONNECTOR_BLOCK__` | YAML-block met `deltaLake:` of `iceberg:` connector-config (incl. metastore + s3-reference) |

Render:

```bash
make render-catalogs
# of direct:
python3 scripts/render-trino-catalogs.py
```

Output gaat naar `rendered/` (gitignored). De parent-kustomization
`platform/09-trino/kustomization.yaml` refereert die rendered files.

## Switching Delta ↔ Iceberg

1. Wijzig `platform-config.yaml` → `table_format: iceberg`.
2. `make render-catalogs && kubectl apply -k platform/09-trino/`.
3. Herbouw dbt-marts: `cd dbt && TABLE_FORMAT=iceberg dbt run`.
4. Spark-jobs herstarten met `TABLE_FORMAT=iceberg`.

Zie [`docs/adr/0002-iceberg-vs-delta.md`](../../../docs/adr/0002-iceberg-vs-delta.md) en
[`docs/adr/0006-delta-chosen-for-this-implementation.md`](../../../docs/adr/0006-delta-chosen-for-this-implementation.md).
