# Superset dashboards

Status: **scaffold + datasets**, geen vooraf-geëxporteerde dashboards in fase 7.

De init-Job ([../init-job.yaml](../init-job.yaml)) registreert Trino als
database en maakt datasets voor UC-01, UC-04, UC-05, UC-06, UC-07 aan.
Dashboards bouwen we vervolgens **interactief** in Superset's UI; export via
`Settings → Import/Export` levert een `.zip` op die hier gecommit kan worden.

## Dashboards die de DoD vereist

- `uc01-wia-funnel.zip` — DoD: "Superset toont dashboard 'WIA Funnel' voor rol `data_steward` met 7 dagen synthetische data."
- `uc06-lastprognose.zip` — Schadelast scenario-vergelijking.

## Workflow voor commits

```bash
# Bouw in UI, exporteer naar zip
# Plaats hier:
cp ~/Downloads/dashboard_export.zip platform/12-superset/dashboards/uc01-wia-funnel.zip

# Re-import op een nieuw cluster:
kubectl -n odap-platform exec deploy/superset-node-default -c superset -- \
  superset import-dashboards -p /tmp/uc01-wia-funnel.zip
```

(Of via REST API `POST /api/v1/dashboard/import` met `multipart/form-data`.)

## Programmatisch maken (TODO)

Voor reproduceerbare CI-deploys kunnen we charts + dashboards declaratief in
Python aanmaken via Superset's API:

```python
# init_dashboards.py — TODO fase 7+
ENDPOINT = "/api/v1/chart/"
BODY_UC01_FUNNEL_LINE = {
    "datasource_id": dataset_id_uc01,
    "datasource_type": "table",
    "viz_type": "line",
    "params": json.dumps({...}),
    "slice_name": "WIA Funnel — aanvragen per dag",
}
```

Niet in fase 7 vanwege de chart-params-complexiteit; volgt zodra Superset's
`assets`-config-bundles stabiel zijn.
