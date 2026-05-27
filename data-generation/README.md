# data-generation

Python-package met synthetische data-generators voor het UWV-referentie-platform.

> **STRIKT SYNTHETISCH.** Geen echte BSN's, geen echte adresgegevens, geen
> echte cliënt-data. Test-BSN-bereik (`9XXXXXXXX`) per BRP-conventie.
> Elke geserialiseerde dataset bevat het header-comment
> `SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE`.

## Generators

| Module | Inhoud |
|---|---|
| `generators.persona` | Persoon (BSN+11-proef, naam, birth_date, adres, geslacht). |
| `generators.polisadministratie` | IKV's per persoon, dienstverbanden, lonen (placeholder, fase 5). |
| `generators.ww` | WW-aanvragen (placeholder, fase 5). |
| `generators.wia` | WIA-aanvragen + beoordelingen (placeholder, fase 5). |
| `generators.wajong` | Wajong-dossiers (placeholder, fase 5). |
| `generators.zw` | Ziektewet-meldingen (placeholder, fase 5). |
| `generators.crm` | Klantcontact (placeholder, fase 5). |
| `generators.fez` | Uitkeringslast-aggregaten (placeholder, fase 6). |

Alle generators delen `generators._common` voor faker, header-stempels, en
deterministische seeding.

## Loaders

| Script | Doel |
|---|---|
| `load_to_s3.py` | Schrijft generator-output als JSONL naar `s3://odap-raw/<domain>/<entity>/dt=YYYY-MM-DD/*.jsonl`. Spark Structured Streaming (file source) pikt dit op. |
| `load_to_minio_staging.py` | Schrijft batch-output naar `s3://odap-staging/` als CSV (placeholder). |

## Lokaal draaien

```bash
cd data-generation
uv sync
uv run python -m generators.persona --count 100
```

## Tests

```bash
uv run pytest                    # of: uv run pytest -v
uv run ruff check generators/    # lint
```

## In-cluster (via seed-job)

`scripts/seed.sh` past `data-generation/k8s/seed-job.yaml` toe op het cluster.
De Job mount de generator-code via twee ConfigMaps en draait `load_to_s3.py`
tegen de in-cluster MinIO (`s3://odap-raw/`).
