# tests/ — Smoke / integration / e2e

Drie test-niveaus, oplopend in scope en doorlooptijd.

| Niveau | Locatie | Wat | Doorlooptijd | Cluster nodig? |
|---|---|---|---|---|
| **Smoke** | [`smoke/`](smoke/) | "Staat het op?" — één component per script. Faalt snel bij infrastructuur-issues. | ~3 min | ja |
| **Integration** | [`integration/`](integration/) | Cross-component flows zonder volledige UC. | — (nog leeg, zie [improvements #1.13](../docs/improvements.md)) | ja |
| **E2E** | [`e2e/`](e2e/) | UC-01 happy path: Kafka → bronze → silver → gold → Superset. | ~10 min | ja |

> dbt-tests (`unique`, `not_null`, custom `bsn_valid`, …) draaien in
> `cd dbt && dbt test` — zie [`../dbt/README.md`](../dbt/README.md).

## Smoke

Doorgenummerd `01`..`09`, in volgorde van afhankelijkheid:

| # | Test | Wat |
|---|---|---|
| 01 | [stackable-up](smoke/01-stackable-up.sh) | Bootstrap-status na `make bootstrap` — namespaces, helm-releases, Keycloak realm, MinIO buckets, Stackable-operators. |
| 02 | [trino-query](smoke/02-trino-query.sh) | Trino + OPA accepteren een simpele query. |
| 03 | [bronze-data](smoke/03-bronze-data.sh) | Synthetische data is door Kafka → Spark → Delta gekomen. |
| 04 | [dbt-parse](smoke/04-dbt-parse.sh) | dbt project parses + compiles. |
| 05 | [airflow-up](smoke/05-airflow-up.sh) | Airflow scheduler healthy, DAGs geparseerd. |
| 06 | [superset-up](smoke/06-superset-up.sh) | Superset init-Job complete, Trino-database geregistreerd. |
| 07 | [openmetadata-up](smoke/07-openmetadata-up.sh) | Classifications + glossary geladen. |
| 08 | [opa-decisions](smoke/08-opa-decisions.sh) | OPA-decisions kloppen with the platform policies. |
| 09 | [portal-up](smoke/09-portal-up.sh) | ODAP Portal bereikbaar achter oauth2-proxy. |

```bash
make smoke                 # alle smoke tests
bash tests/smoke/02-trino-query.sh   # eentje individueel
```

`run-smoke-tests.sh` faalt on the **eerste** test die non-zero exit geeft —
geen "doorgaan en optellen aan het eind".

## E2E

| Test | Wat |
|---|---|
| [`full-flow-uc01.sh`](e2e/full-flow-uc01.sh) | UC-01 WIA Funnel: seed → Kafka → bronze → dbt run staging+marts → Superset-dashboard reachable. |
| [`fast-e2e.sh`](e2e/fast-e2e.sh) | Smoke 01-08 + UC-01 verify (skip seed als data al aanwezig is). |

```bash
make e2e                   # = full-flow-uc01.sh
bash tests/e2e/fast-e2e.sh # snellere variant
```

## Integration

Map is **leeg**. Bedoeld voor cross-component tests die meer doen dan smoke
maar minder dan e2e — bijvoorbeeld OPA-row-filter ↔ Trino-query, of
NiFi-flow ↔ Kafka-topic ↔ Spark-consumer.

Zie [`docs/improvements.md`](../docs/improvements.md) item 1.13 for the open
vraag waar de eerste integration-tests aan moeten voldoen.

## Conventies

- Bash, `set -euo pipefail` aan de top, kleurige `log()`/`warn()`/`fail()`.
- **Geen** asserties die leesgedrag aanpassen (`grep -q` ✓; `read -r` ✗
  in een loop zonder timeout).
- Output: één kop per stap (`==> <stap>`), één regel `OK` / `FAIL` per
  assertion, en een eind-regel with the totaaltelling.
- Geen vaste timeouts — gebruik `kubectl wait --timeout=…` of polling met
  `for i in $(seq 1 60)`.
- Tests gaan ervan uit dat de **default kubectl-context** het juiste cluster
  is. Voor AKS: eerst `make aks-context`.

## Toevoegen van een nieuwe test

1. Smoke: kies het volgende vrije nummer en sluit aan on the naamconventie
   `NN-<component>-<wat>.sh`. Test-script eindigt met
   `echo "OK"` on the laatste regel.
2. Integration / e2e: één scenario per script, `<scenario>.sh`. Linken vanuit
   deze README en het [Makefile](../Makefile) als de test eigen target verdient.

## CI

Smoke draait op iedere PR via [`ci/github-actions/`](../ci/github-actions/)
(in opzet — zie [`ci/`](../ci/)).
