# ADR-0010: platform-config.yaml als single source of truth

| Status | **Geaccepteerd** |
|---|---|
| Datum | 2026-05-21 |
| Beslissers | Platform Architect, Data Engineer |
| Gerelateerd | ADR-0002, ADR-0006 (table_format), ADR-0007 (Airflow) |

---

## Context

`platform-config.yaml` (repo-root) is sinds dag-1 bedoeld als centrale
plek voor implementatie-keuzes die meerdere components beïnvloeden:
table_format, catalog_backend, object_store, bucket-namen, DNS-suffix
per mode. De header van het bestand zegt:

> Eén bron van waarheid voor implementatie-keuzes die door meerdere
> components worden gelezen (Trino-catalogs, dbt-macros, Spark-env,
> NiFi-templates, Airflow-DAGs). Wijzig hier — niet hardcoden in
> components.

In de praktijk werd dit ondergeconsumeerd. De audit van 2026-05-21
vond drie duidelijke divergenties:

1. **Spark** hardcodeerde `TABLE_FORMAT: "delta"` in
   `platform/08-spark/apps/streaming-bronze.yaml`.
2. **DNS-modes** werden in `scripts/lib/mode.sh` (regel 68-81) hardcoded
   in een case-statement, terwijl `platform-config.yaml::dns.modes`
   exact dezelfde mapping bevatte.
3. **Bucket-namen** zaten verspreid over manifests en scripts; de keys
   in `platform-config.yaml::buckets` werden zelden geraadpleegd.

Dit voelt klein totdat je een Iceberg-experiment doet
(`table_format: iceberg`) en ontdekt dat Spark stiekem op Delta
doorgaat omdat zijn env-var niet meekomt.

## Beslissing

We maken `platform-config.yaml` runtime-consumeerbaar via een gespiegelde
ConfigMap **`platform-config`** in namespace `odap-platform`. Bron en
spiegel hebben gelijke keys; **bij wijziging update je beide**.

```
platform-config.yaml  (repo-root)        platform-config-cm.yaml  (00-namespaces)
─────────────────────────────────         ────────────────────────────────────────
platform.table_format ───────────────►   data.TABLE_FORMAT
platform.catalog_backend ───────────►    data.CATALOG_BACKEND
buckets.bronze ────────────────────►     data.BUCKET_BRONZE
…                                         …
```

**Consumptie-patronen** per laag:

| Laag | Hoe het de config leest |
|---|---|
| Python scripts (render-trino-catalogs, mode.sh) | Lezen direct uit `platform-config.yaml` on the filesystem (build-time) |
| Spark (driver+executor) | `envFrom: configMapRef: platform-config` injecteert alle keys als env-vars |
| Airflow (DAGs + tasks) | `kubernetesExecutors.envFrom: configMapRef: platform-config` (zie [`airflowcluster.yaml`](../../platform/11-airflow/airflowcluster.yaml)) |
| dbt | Macros lezen via `env_var('TABLE_FORMAT', 'delta')`; Airflow injects |
| Trino-catalogs | Gerendered door `scripts/render-trino-catalogs.py` op deploy-time uit `platform-config.yaml` |

## Alternatieven overwogen

1. **Eén centrale ConfigMap, geen YAML-file.** Verworpen: build-time
   scripts (render-trino-catalogs, mode.sh) lezen vóór er een cluster
   is. YAML-bestand blijft nodig.
2. **Jinja-render een ConfigMap.yaml uit platform-config.yaml.**
   Aantrekkelijk — geen drift mogelijk. Verworpen voor nu: te complex
   voor één keer per deploy, te lastig in code-review (gegenereerde
   YAML in PR's). Mogelijk een latere uitbreiding.
3. **Helm-chart voor platform-config.** Helm voegt little waarde voor
   één ConfigMap; we hebben al een kustomize-only-platform en willen
   geen tweede tooling erbij.

## Consequenties

**Positief:**
- Format-experimenten (Iceberg vs Delta) kunnen via één YAML-edit
  worden uitgerold.
- Cloud-mode-domain swaps werken consistent (mode.sh leest dezelfde
  bron als ConfigMap).
- Nieuwe components weten waar te kijken (`envFrom: platform-config`).

**Negatief / mitigaties:**
- **Drift-risico**: YAML en ConfigMap kunnen out-of-sync raken.
  Mitigatie: CI-check `ci/scripts/check-platform-config-sync.py`
  (TODO; specificeert te valideren key-pairs) faalt als ze divergeren.
- **Twee-staps-edit**: bij wijziging update je beide. Mitigatie:
  pre-commit-hint of (toekomstig) een `make sync-platform-config`
  target die de YAML to the ConfigMap kopieert.

## Migratie & evidence

1. `platform/00-namespaces/platform-config-cm.yaml` (nieuw) — ConfigMap
   met alle huidige keys.
2. `platform/08-spark/apps/streaming-bronze.yaml` — `envFrom: configMapRef`
   ipv hardcoded `TABLE_FORMAT`.
3. Toekomst: `platform/11-airflow/airflowcluster.yaml` + andere
   components geleidelijk migreren.
4. CI-gate landt in `ci/scripts/check-platform-config-sync.py` zodra
   PR's beginnen te driften.
